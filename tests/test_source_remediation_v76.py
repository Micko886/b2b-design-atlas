"""V76: actual site/module editorial remediation in packaged public catalog.

Tests read output from the same deployment archive and curated build step.
They never modify CMS users, draft history, publishing or Postgres.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import seo_routes,seo_final_audit
import curate_editorial_v76 as curate

class EditorialSourcesV76(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads(curate.SOURCE.read_text(encoding="utf-8"))
        cls.modules=json.loads(curate.MODULES.read_text(encoding="utf-8"))
        cls.sites={row["id"]:row for row in cls.source["sites"]}
        cls.by_id={row["id"]:row for row in cls.modules}
        cls.notes={row["id"]:row for row in cls.source["notes"]}
        cls.public=seo_routes.base_catalog()

    def test_six_real_website_summaries_have_substantive_context(self):
        self.assertEqual(len(curate.SITES),6)
        for slug,(official,summary) in curate.SITES.items():
            with self.subTest(site=slug):
                src=self.sites[slug]
                self.assertEqual(src["url"],official)
                self.assertEqual(src["summary"],summary)
                self.assertGreaterEqual(len(summary),90)
                self.assertIn(slug,self.public["sites"])
                self.assertEqual(self.public["sites"][slug]["summary"],summary)
                self.assertTrue(seo_routes.source_url(official))
                self.assertTrue(src["name"])
                self.assertTrue(src["takeaway"])

    def test_eighteen_module_summaries_are_distinct_from_titles(self):
        self.assertEqual(len(curate.MODULES_EDIT),18)
        for mid,(site,title,summary,lesson) in curate.MODULES_EDIT.items():
            with self.subTest(module=mid):
                row=self.by_id[mid]
                self.assertEqual(row["site_id"],site)
                self.assertEqual(row["title"],title)
                self.assertEqual(row["summary"],summary)
                self.assertEqual(row["lesson"],lesson)
                self.assertNotEqual(summary.strip(),title.strip())
                self.assertGreaterEqual(len(summary),70)
                self.assertGreaterEqual(len(lesson),32)
                self.assertTrue(seo_routes.source_url(row["url"]))
                self.assertIn(site,self.sites)
                self.assertEqual(self.public["modules"][mid]["summary"],summary)

    def test_notes_remain_consistent_for_build_generated_modules(self):
        for mid,(*_,summary,lesson) in curate.MODULES_EDIT.items():
            if mid not in self.notes:
                continue
            with self.subTest(note=mid):
                self.assertEqual(self.notes[mid]["summary"],summary)
                self.assertEqual(self.notes[mid]["lesson"],lesson)

    def test_existing_catalog_counts_and_relationships_stay_intact(self):
        self.assertEqual(len(self.sites),85)
        self.assertEqual(len(self.modules),175)
        self.assertEqual(len(self.public["patterns"]),20)
        self.assertGreaterEqual(len(self.public["articles"]),13)
        self.assertEqual(len(self.by_id),len(self.modules))
        for module in self.modules:
            with self.subTest(module=module["id"]):
                self.assertIn(module["site_id"],self.sites)
                self.assertIn(module["id"],self.public["modules"])
        for pattern in self.public["patterns"].values():
            for mid in pattern.get("modules",[]):
                self.assertIn(mid,self.by_id)

    def test_all_selected_captured_images_remain_real_files(self):
        images=curate.BASE/"screenshots"/"modules"
        for mid in curate.MODULES_EDIT:
            with self.subTest(module=mid):
                item=self.by_id[mid]
                filename=item.get("image_file")
                self.assertIsInstance(filename,str)
                self.assertTrue((images/filename).is_file(),mid)
        originals=curate.BASE/"screenshots"/"sites"
        # These two source records currently have no genuine site screenshot.
        # Keep neutral fallbacks; never invent or borrow an image for them.
        for sid in ("molex","festo"):
            self.assertFalse((originals/(sid+".webp")).exists(),sid)
            self.assertFalse(self.sites[sid].get("screenshot_url"))
        for sid in curate.SITES:
            if sid not in ("molex","festo"):
                self.assertTrue((originals/(sid+".webp")).is_file(),sid)

    def test_public_detail_pages_show_real_revised_text_and_valid_source_links(self):
        for sid in curate.SITES:
            with self.subTest(site=sid):
                url="/websites/"+sid
                record=seo_routes.seo_record(url,self.public)
                self.assertEqual(record["description"],curate.SITES[sid][1])
                self.assertTrue(record["indexed"])
                page=seo_routes.public_prerender(url,record,self.public)
                self.assertIn(curate.SITES[sid][1],page)
                self.assertIn('href="'+self.sites[sid]["url"]+'"',page)
                self.assertNotIn('href="javascript:',page)
        for mid in curate.MODULES_EDIT:
            with self.subTest(module=mid):
                path="/sections/"+mid
                record=seo_routes.seo_record(path,self.public)
                self.assertTrue(record and record["indexed"])
                page=seo_routes.public_prerender(path,record,self.public)
                self.assertIn(self.by_id[mid]["summary"],page)
                self.assertIn(self.by_id[mid]["lesson"],page)
                self.assertIn('href="/websites/'+self.by_id[mid]["site_id"]+'"',page)

    def test_justified_thin_site_warning_is_resolved_not_faked(self):
        record=self.sites["sick"]
        self.assertGreaterEqual(
            len(record.get("summary",""))+
            len(record.get("focus",""))+
            len(record.get("model",""))+
            len(record.get("visual_style","")),95)
        audit=seo_final_audit.analyze(self.public,kind_filter="site",limit=60)
        row=next((x for x in audit["items"] if x["slug"]=="sick"),None)
        if row:
            self.assertNotIn("depth",{issue["code"] for issue in row["issues"]})

    def test_replay_is_idempotent_and_does_not_change_record_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"source_index.json"
            modules=Path(folder)/"module_catalog.json"
            source.write_text(curate.SOURCE.read_text(encoding="utf-8"),encoding="utf-8")
            modules.write_text(curate.MODULES.read_text(encoding="utf-8"),encoding="utf-8")
            before_s=json.loads(source.read_text(encoding="utf-8"))
            before_m=json.loads(modules.read_text(encoding="utf-8"))
            with patch.object(curate,"SOURCE",source),patch.object(curate,"MODULES",modules):
                curate.main()
                first=(source.read_bytes(),modules.read_bytes())
                curate.main()
                self.assertEqual(first,(source.read_bytes(),modules.read_bytes()))
            after_s=json.loads(source.read_text(encoding="utf-8"))
            after_m=json.loads(modules.read_text(encoding="utf-8"))
            for old,new in zip(before_s["sites"],after_s["sites"]):
                for key in ("id","url","name","sector","featured","curation_batch"):
                    self.assertEqual(old.get(key),new.get(key))
            for old,new in zip(before_m,after_m):
                for key in ("id","site_id","url","image_file","source_capture","crop_px"):
                    self.assertEqual(old.get(key),new.get(key))

if __name__=="__main__":
    unittest.main()
