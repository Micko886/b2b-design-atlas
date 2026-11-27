"""V53.2 · Real media API and SQL lifecycle tests, isolated from production."""
import base64
import json
import uuid
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from app import cms_routes
from test_cms_v514 import DB

PNG=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBAeKf3UYAAAAASUVORK5CYII=")


class MediaWorkBenchV532(unittest.TestCase):
    def setUp(self):
        self.db=DB()
        self.uid=str(uuid.uuid4())
        self.db.execute("INSERT INTO atlas_users(id,email,display_name,created_at) VALUES(?,?,?,?)",
                        (self.uid,"editor@qa.test","Editor","2026-11-26"))
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(cms_routes,"ensure_cms"))
        self.stack.enter_context(patch.object(cms_routes.user_auth,"db",return_value=self.db))
        self.require=self.stack.enter_context(
            patch.object(cms_routes,"require_admin",return_value={"user_id":self.uid}))
        app=FastAPI()
        cms_routes.register_cms_routes(app)
        self.routes={(route.path,method):route.endpoint for route in app.routes
                     for method in (route.methods or set())}

    def call(self,method,path,*args,**kwargs):
        return self.routes[(path,method)](*args,**kwargs)

    def upload(self,name):
        return self.call("POST","/api/admin/media",
                         cms_routes.MediaUpload(name=name,mime="image/png",
                                                content=base64.b64encode(PNG).decode()),object())

    def listing(self,**filters):
        return self.call("GET","/api/admin/media",object(),**filters)

    def attach_to_draft(self,media_id,kind="site",slug="ref-site",published=False):
        url="/api/media/"+media_id
        payload={"id":slug,"name":"Reference","url":"https://example.org",
                 "sector":"Industrial","summary":"Work","screenshot_url":url}
        self.db.execute("""INSERT INTO atlas_cms_entries
            (kind,slug,draft_json,published_json,status,revision,created_by,updated_by,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (kind,slug,json.dumps(payload),json.dumps(payload) if published else None,
             "published" if published else "draft",1,self.uid,self.uid,"2026-11-26","2026-11-26"))

    def test_search_and_paginate_across_all_stored_images(self):
        ids=[self.upload("concept-"+str(i)+".png")["id"] for i in range(161)]
        first=self.listing(limit=24,offset=0)
        self.assertEqual(first["total"],161)
        self.assertEqual(len(first["items"]),24)
        self.assertTrue(first["has_more"])
        older=self.listing(limit=24,offset=144)
        self.assertEqual(len(older["items"]),17)
        self.assertFalse(older["has_more"])
        all_ids={item["id"] for page in range(7)
                 for item in self.listing(limit=24,offset=page*24)["items"]}
        self.assertEqual(all_ids,set(ids))
        matched=self.listing(q="concept-160.png")
        self.assertEqual(matched["total"],1)
        self.assertEqual(matched["items"][0]["file_name"],"concept-160.png")

    def test_metadata_search_caption_and_seo_state(self):
        media=self.upload("factory-picture.png")
        a=media["id"]
        result=self.call("PUT","/api/admin/media/{media_id}/metadata",a,
                         cms_routes.MediaMetadata(alt_text="  CNC machining equipment  ",
                             caption="  Product engineering photo  "),object())
        self.assertEqual(result["alt_text"],"CNC machining equipment")
        self.assertEqual(self.listing(seo="ready")["total"],1)
        self.assertEqual(self.listing(seo="missing")["total"],0)
        self.assertEqual(self.listing(q="machining")["items"][0]["id"],a)
        self.assertEqual(self.listing(q="ENGINEERING")["items"][0]["caption"],"Product engineering photo")
        self.assertEqual(self.listing(file_type="webp")["total"],0)
        self.assertEqual(self.listing(file_type="png")["total"],1)
        self.require.assert_any_call(unittest.mock.ANY,mutate=True,permission="media")

    def test_usage_filter_includes_draft_and_published_snapshots_and_links(self):
        draft=self.upload("in-draft.png")
        published=self.upload("published.png")
        unused=self.upload("orphan.png")
        self.attach_to_draft(draft["id"],slug="draft-page")
        self.attach_to_draft(published["id"],slug="published-page",published=True)
        used=self.listing(usage="used")
        self.assertEqual(used["total"],2)
        self.assertEqual(self.listing(usage="unused")["total"],1)
        info=next(x for x in used["items"] if x["id"]==published["id"])
        self.assertEqual(info["used_by"],[{"kind":"site","slug":"published-page"}])
        self.assertEqual(self.listing(q="draft-page")["total"],1)
        self.assertEqual(self.listing(q="orphan.png")["items"][0]["id"],unused["id"])

    def test_bulk_delete_is_atomic_when_any_image_has_live_reference(self):
        safe=self.upload("safe.png")
        used=self.upload("used.png")
        self.attach_to_draft(used["id"],slug="bound")
        with self.assertRaises(HTTPException) as err:
            self.call("POST","/api/admin/media/bulk-delete",
                      cms_routes.MediaBulkDelete(ids=[safe["id"],used["id"]]),object())
        self.assertEqual(err.exception.status_code,409)
        self.assertEqual(self.listing()["total"],2)
        self.assertIsNotNone(self.db.one("SELECT id FROM atlas_cms_media WHERE id=?",(safe["id"],)))

    def test_delete_unused_images_together_and_remove_metadata(self):
        a=self.upload("one.png")
        b=self.upload("two.png")
        self.call("PUT","/api/admin/media/{media_id}/metadata",a["id"],
                  cms_routes.MediaMetadata(alt_text="Warehouse illustration"),object())
        result=self.call("POST","/api/admin/media/bulk-delete",
                         cms_routes.MediaBulkDelete(ids=[a["id"],b["id"]]),object())
        self.assertEqual(result,{"ok":True,"deleted":2})
        self.assertEqual(self.listing()["total"],0)
        self.assertFalse(self.db.all("SELECT * FROM atlas_cms_media_meta"))

    def test_invalid_bulk_requests_and_search_are_rejected(self):
        a=self.upload("only.png")
        for ids in ([a["id"],a["id"]],[a["id"],"../incorrect"],[str(uuid.uuid4())]):
            with self.subTest(ids=ids),self.assertRaises(HTTPException) as err:
                self.call("POST","/api/admin/media/bulk-delete",
                          cms_routes.MediaBulkDelete(ids=ids),object())
            self.assertIn(err.exception.status_code,(404,422))
        for filters in ({"usage":"untrusted"},{"file_type":"svg"},{"seo":"unknown"},
                        {"offset":-1},{"limit":151},{"q":"x"*161}):
            with self.subTest(filters=filters),self.assertRaises(HTTPException) as err:
                self.listing(**filters)
            self.assertEqual(err.exception.status_code,422)
        with self.assertRaises(ValidationError):
            cms_routes.MediaBulkDelete(ids=[])
        with self.assertRaises(ValidationError):
            cms_routes.MediaMetadata(alt_text="a"*241)

    def test_single_delete_preserves_reference_guard(self):
        a=self.upload("cover.png")
        self.attach_to_draft(a["id"],slug="published-story",published=True)
        with self.assertRaises(HTTPException) as err:
            self.call("DELETE","/api/admin/media/{media_id}",a["id"],object())
        self.assertEqual(err.exception.status_code,409)
        self.assertEqual(self.listing()["total"],1)

    def test_metadata_is_not_published_into_existing_article_fields(self):
        a=self.upload("alt.png")
        self.call("PUT","/api/admin/media/{media_id}/metadata",a["id"],
                  cms_routes.MediaMetadata(alt_text="New recommended ALT"),object())
        # The metadata lives on the asset, not in the public content payload.
        self.assertEqual(self.listing()["items"][0]["alt_text"],"New recommended ALT")
        self.assertEqual(self.db.all("SELECT * FROM atlas_cms_entries"),[])

    def test_bulk_alt_fills_two_missing_preserves_caption_and_public_payload(self):
        one=self.upload("machine.png")
        two=self.upload("workshop.png")
        self.attach_to_draft(one["id"],slug="public-example",published=True)
        public_before=self.db.one(
            "SELECT draft_json,published_json FROM atlas_cms_entries WHERE slug=?",
            ("public-example",))
        self.call("PUT","/api/admin/media/{media_id}/metadata",one["id"],
                  cms_routes.MediaMetadata(alt_text="",caption="Original photographer"),object())
        payload=cms_routes.MediaBulkAlt(items=[
            cms_routes.MediaBulkAltItem(id=one["id"],alt_text="Industrial machine control panel"),
            cms_routes.MediaBulkAltItem(id=two["id"],alt_text="Metalworking workshop interior")])
        result=self.call("POST","/api/admin/media/bulk-alt",payload,object())
        self.assertEqual(result["updated"],2)
        ready=self.listing(seo="ready")
        self.assertEqual(ready["total"],2)
        info=next(x for x in ready["items"] if x["id"]==one["id"])
        self.assertEqual(info["caption"],"Original photographer")
        self.assertEqual(info["usage_count"],1)
        public_after=self.db.one(
            "SELECT draft_json,published_json FROM atlas_cms_entries WHERE slug=?",
            ("public-example",))
        self.assertEqual(public_before,public_after)
        self.require.assert_any_call(unittest.mock.ANY,mutate=True,permission="media")

    def test_bulk_alt_rejects_a_stale_item_atomically(self):
        first=self.upload("new.png")
        second=self.upload("edited.png")
        self.call("PUT","/api/admin/media/{media_id}/metadata",second["id"],
                  cms_routes.MediaMetadata(alt_text="Already described",caption="Keep this"),object())
        payload=cms_routes.MediaBulkAlt(items=[
            cms_routes.MediaBulkAltItem(id=first["id"],alt_text="First image"),
            cms_routes.MediaBulkAltItem(id=second["id"],alt_text="Overwritten image")])
        with self.assertRaises(HTTPException) as err:
            self.call("POST","/api/admin/media/bulk-alt",payload,object())
        self.assertEqual(err.exception.status_code,409)
        self.assertEqual(self.listing(seo="missing")["total"],1)
        self.assertEqual(self.db.one(
            "SELECT alt_text,caption FROM atlas_cms_media_meta WHERE media_id=?",
            (second["id"],)),{"alt_text":"Already described","caption":"Keep this"})
        self.assertIsNone(self.db.one("SELECT * FROM atlas_cms_media_meta WHERE media_id=?",
                                       (first["id"],)))

    def test_bulk_alt_rejects_missing_ids_and_duplicates_before_writing(self):
        existing=self.upload("valid.png")
        missing=str(uuid.uuid4())
        for ids,expected_status in (
            ([existing["id"],missing],404),
            ([existing["id"],existing["id"]],422),
            ([existing["id"],"x"*36],422),
        ):
            with self.subTest(ids=ids),self.assertRaises(HTTPException) as err:
                payload=cms_routes.MediaBulkAlt(items=[
                    cms_routes.MediaBulkAltItem(id=id,alt_text="Meaningful image description")
                    for id in ids])
                self.call("POST","/api/admin/media/bulk-alt",payload,object())
            self.assertEqual(err.exception.status_code,expected_status)
            self.assertEqual(self.listing(seo="missing")["total"],1)
        self.assertFalse(self.db.all("SELECT * FROM atlas_cms_media_meta"))

    def test_bulk_alt_has_strict_item_and_text_limits(self):
        item_id=str(uuid.uuid4())
        with self.assertRaises(ValidationError):
            cms_routes.MediaBulkAlt(items=[])
        with self.assertRaises(ValidationError):
            cms_routes.MediaBulkAlt(items=[
                cms_routes.MediaBulkAltItem(id=item_id,alt_text="description")
                for _ in range(21)])
        with self.assertRaises(ValidationError):
            cms_routes.MediaBulkAltItem(id=item_id,alt_text="x"*241)
        self.upload("blank.png")
        payload=cms_routes.MediaBulkAlt(items=[
            cms_routes.MediaBulkAltItem(id=self.listing()["items"][0]["id"],alt_text="  ")])
        with self.assertRaises(HTTPException) as err:
            self.call("POST","/api/admin/media/bulk-alt",payload,object())
        self.assertEqual(err.exception.status_code,422)
        self.assertEqual(self.listing(seo="missing")["total"],1)



if __name__=="__main__":
    unittest.main()
