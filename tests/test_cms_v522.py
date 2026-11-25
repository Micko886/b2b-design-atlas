"""V52 · Content editing workflow and media selection regression contracts."""
import re
import unittest
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from unittest.mock import patch
import base64
from test_cms_v514 import DB
from app import cms_routes

STATIC=Path("/srv/atlas/static")


class FocusedEditorContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(STATIC/"cms.html").read_text(encoding="utf-8")
        cls.js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets/cms.css").read_text(encoding="utf-8")

    def test_content_list_and_editor_are_separate_modes(self):
        for text in ("function setStudioMode(editing)","function closeEditor(push=true)",
                     'data-close-editor','data-editor-save','data-editor-submit',
                     "setStudioMode(true)","setStudioMode(false)",
                     "history.pushState({},'',editorUrl(slug))"):
            with self.subTest(text=text):self.assertIn(text,self.js)
        self.assertIn("cms-split.cms-editing .cms-browser{display:none}",self.css)
        self.assertIn("cms-split:not(.cms-editing) .cms-editor{display:none}",self.css)

    def test_website_editor_starts_with_fields_and_image_not_dashboard(self):
        for required in ("function siteEditorForm(values,editable)",
                         "cms-easy-layout","cms-easy-visual","cms-easy-header",
                         "cms-easy-advanced","cms-easy-mode",
                         "document.body.classList.toggle('cms-editor-active'",
                         "syncSiteTitle()"):
            with self.subTest(required=required):
                self.assertIn(required,self.js)
        self.assertIn("body.cms-editor-active .atlas-v521-page-head",self.css)
        self.assertIn("body.cms-editor-active .atlas-v521-quicknav",self.css)
        self.assertIn(".cms-easy-mode .cms-easy-layout",self.css)
        self.assertIn("item.kind==='site'?siteHeader:content+steps+meta",self.js)
        self.assertIn("item.kind==='site'?'':'<div class=\"cms-form-group-label\"",self.js)
        self.assertIn("item.kind==='site'?siteEditorForm(values,editable)",self.js)
        self.assertIn("item.kind==='site'?'':'<details class=\"cms-json-advanced\"",self.js)
        self.assertIn("type==='lines')base[name]=value.split('\\n')",self.js)

    def test_website_auto_save_and_status_update_remain_connected(self):
        self.assertIn("id=\"cms-autosave-status\"",self.js)
        self.assertIn("cms-easy-save-note",self.js)
        self.assertIn("function markDraftDirty()",self.js)
        self.assertIn("persistDraft(true)",self.js)
        self.assertIn(".cms-easy-header-side .cms-item-state",self.js)
        self.assertIn("syncSiteImage();refreshArticlePreview()",self.js)

    def test_site_gallery_can_add_sort_remove_and_set_cover(self):
        for text in ("function galleryCards(items)","function galleryValue()", "function addGalleryImages(urls)",
                     "data-gallery-add", "data-gallery-cover", "data-gallery-remove", "data-gallery-move",
                     "data-gallery-label", "state.mediaField='field-gallery'", "uploadedUrls.push(lastUrl)",
                     "if(state.mediaField==='field-gallery')", "galleryCards(Array.isArray(values.gallery)"):
            with self.subTest(text=text):self.assertIn(text,self.js)
        self.assertIn("cms-gallery-editor",self.css)
        self.assertIn("data-field=\"gallery\"",self.js)


    def test_media_file_chooser_is_a_real_button(self):
        self.assertIn('id="cms-media-select"',self.html)
        self.assertIn('id="cms-media-file"',self.html)
        self.assertIn("$('#cms-media-select').addEventListener('click'",self.js)
        self.assertIn("await uploadMedia(files)",self.js)
        self.assertIn("上传完成：成功 ",self.js)
        self.assertIn("message(original.name+' 上传失败：'",self.js)

    def test_uploaded_images_have_an_explicit_destination(self):
        for field in ("cover_image","screenshot_url"):
            self.assertIn(field,self.js)
        self.assertIn("data-editor-pick-media",self.js)
        self.assertIn("state.mediaField",self.js)
        self.assertIn("document.getElementById(state.mediaField)",self.js)
        self.assertIn("media_urls=[document.get(\"cover_image\",\"\")",Path(cms_routes.__file__).read_text(encoding="utf-8"))

    def test_cache_busted_and_no_single_node_iteration(self):
        self.assertIn("cms.js?v=5230",self.html)
        self.assertIn("cms.css?v=5230",self.html)
        self.assertEqual(re.findall(r"for\s*\([^)]*\bof\s+\$\(",self.js),[])


class ScreenshotMediaValidation(unittest.TestCase):
    @staticmethod
    def site_payload(photo):
        return dict(id="site-example",name="Demo",url="https://example.com",
                    sector="Industrial",summary="Site description",screenshot_url=photo)

    def test_uploaded_image_is_accepted_as_site_screenshot(self):
        image="/api/media/"+str(uuid.uuid4())
        payload=cms_routes.cleaned("site","site-example",self.site_payload(image))
        self.assertEqual(payload["screenshot_url"],image)

    def test_untrusted_screenshot_url_is_rejected(self):
        for image in ("javascript:alert(1)","https://evil.example/screenshot.png",
                      "/api/media/not-a-uuid","/screenshots/../private.png"):
            with self.subTest(image=image),self.assertRaises(HTTPException):
                cms_routes.cleaned("site","site-example",self.site_payload(image))

    def test_website_gallery_accepts_valid_multiple_images(self):
        payload=self.site_payload('/screenshots/sites/example.webp')
        payload['gallery']=[{'url':'/screenshots/research/example-home.jpg','label':'首页'},
                            {'url':'/api/media/'+str(uuid.uuid4()),'label':'产品页'}]
        result=cms_routes.cleaned('site','site-example',payload)
        self.assertEqual(len(result['gallery']),2)

    def test_website_gallery_rejects_external_duplicate_and_oversize(self):
        base=self.site_payload('/screenshots/sites/example.webp')
        entries=[{'url':'https://evil.example/pic.png','label':'bad'}]
        cases=[entries,[{'url':'/screenshots/../secret.png','label':'x'}],
               [{'url':'/api/media/not-a-uuid','label':'bad'}],
               [{'url':'/screenshots/sites/example.webp','label':'1'},
                {'url':'/screenshots/sites/example.webp','label':'2'}],
               [{'url':'/screenshots/sites/img'+str(i)+'.webp','label':'x'} for i in range(17)]]
        for case in cases:
            with self.subTest(case=case[:2]),self.assertRaises(HTTPException):
                cms_routes.cleaned('site','site-example',{**base,'gallery':case})

    def test_source_capture_remains_statically_constrained(self):
        payload=self.site_payload("/screenshots/sites/example.webp")
        payload["source_capture"]="/api/media/"+str(uuid.uuid4())
        with self.assertRaises(HTTPException):
            cms_routes.cleaned("site","site-example",payload)



class MediaUploadRoundTrip(unittest.TestCase):
    def setUp(self):
        self.db=DB()
        self.uid=str(uuid.uuid4())
        self.db.execute("INSERT INTO atlas_users(id,email,display_name,created_at) VALUES(?,?,?,?)",
                        (self.uid,"editor@example.com","Editor","2026-11-25"))
        app=FastAPI()
        cms_routes.register_cms_routes(app)
        self.routes={(route.path,method):route.endpoint
                     for route in app.routes for method in (route.methods or set())}

    def test_authorized_image_upload_returns_a_reusable_public_url(self):
        # Real transparent 1x1 PNG; upload is intentionally content-addressed by UUID.
        png=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBAeKf3UYAAAAASUVORK5CYII=")
        data=cms_routes.MediaUpload(name="cover.png",mime="image/png",
                                    content=base64.b64encode(png).decode("ascii"))
        with patch.object(cms_routes,"require_admin",return_value={"user_id":self.uid}),\
             patch.object(cms_routes,"ensure_cms"),\
             patch.object(cms_routes.user_auth,"db",return_value=self.db):
            created=self.routes[("/api/admin/media","POST")](data,object())
            self.assertRegex(created["url"],r"^/api/media/[0-9a-f-]{36}$")
            self.assertEqual(created["mime"],"image/png")
            response=self.routes[("/api/media/{media_id}","GET")](created["id"])
            self.assertEqual(response.body,png)
            self.assertEqual(response.media_type,"image/png")

    def test_mismatched_file_type_is_rejected(self):
        data=cms_routes.MediaUpload(name="fake.webp",mime="image/webp",
                                    content=base64.b64encode(b"not a webp file").decode("ascii"))
        with patch.object(cms_routes,"require_admin",return_value={"user_id":self.uid}),\
             patch.object(cms_routes,"ensure_cms"):
            with self.assertRaises(HTTPException) as error:
                self.routes[("/api/admin/media","POST")](data,object())
        self.assertEqual(error.exception.status_code,422)

if __name__=="__main__":
    unittest.main()
