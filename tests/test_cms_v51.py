"""V51 contract: safe article image URLs, content structure and bulk bounds."""
import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from app import cms_routes

class V51ContractTests(unittest.TestCase):
    def article(self):
        return {"id":"editorial-sample","title":"示例文章","subtitle":"摘要","category":"methods",
                "author":"Atlas 编辑部","sections":[{"title":"正文","paragraphs":["内容段落"],"bullets":[],"callout":""}],
                "tags":["设计","研究"],"cover_image":"/api/media/4255210d-d19f-46db-a0ef-ad75ddb3ff3f"}

    def test_persisted_media_cover_is_allowed(self):
        result=cms_routes.cleaned("article","editorial-sample",self.article())
        self.assertEqual(result["category"],"methods")

    def test_external_cover_is_rejected(self):
        payload=self.article()
        payload["cover_image"]="https://attacker.example/pic.svg"
        with self.assertRaises(HTTPException) as error:
            cms_routes.cleaned("article","editorial-sample",payload)
        self.assertEqual(error.exception.status_code,422)

    def test_oversized_bulk_is_rejected(self):
        with self.assertRaises(ValidationError):
            cms_routes.BulkChange(kind="article",action="submit",
                items=[{"slug":f"item-{i}","expected_revision":1} for i in range(21)])

    def test_duplicate_bulk_slugs_are_not_silently_deduplicated(self):
        # Model accepts identifiers; route checks duplicates before mutation.
        data=cms_routes.BulkChange(kind="article",action="publish",
             items=[{"slug":"sample","expected_revision":1},{"slug":"sample","expected_revision":1}])
        self.assertEqual(len(data.items),2)

    def test_invalid_mime_is_rejected(self):
        with self.assertRaises(ValidationError):
            cms_routes.MediaUpload(name="bad.svg",mime="image/svg+xml",content="A"*20)

    def test_absent_sections_rejected(self):
        payload=self.article()
        payload["sections"]=[]
        with self.assertRaises(HTTPException):
            cms_routes.cleaned("article","editorial-sample",payload)

if __name__=="__main__":
    unittest.main()
