#!/usr/bin/env python3
"""Attempt consent-aware real recapture for selected V2.1 visual candidates."""
import asyncio,io,json,re
from pathlib import Path
from PIL import Image,ImageStat,ImageChops
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
SHOTS=ROOT/'screenshots'
TARGETS=[
 ("vast","https://www.vastspace.com/"),
 ("zipline","https://www.zipline.com/"),
 ("form-energy","https://formenergy.com/"),
 ("cfs-energy","https://www.cfs.energy/"),
]
REJECT=re.compile(r'reject|decline|deny|necessary|essential|do not accept|manage.*privacy',re.I)
ACCEPT=re.compile(r'accept all|agree|allow all|accept cookies|accept and continue|okay|got it',re.I)
async def click_consent(page):
 for _ in range(3):
  for pattern in [REJECT,ACCEPT]:
   for frame in page.frames:
    try:
     button=frame.get_by_role('button',name=pattern).first
     if await button.count() and await button.is_visible(timeout=450):
      label=(await button.inner_text(timeout=500)).strip()[:90]
      await button.click(timeout=2200)
      await page.wait_for_timeout(700)
      return label
    except Exception:pass
  await page.wait_for_timeout(600)
 return None
async def snap(page,y):
 await page.evaluate('(y)=>window.scrollTo({top:y,behavior:"instant"})',y)
 await page.wait_for_timeout(850)
 return Image.open(io.BytesIO(await page.screenshot(type='png',full_page=False,animations='disabled'))).convert('RGB')
def store(im,path):
 im.save(path,'WEBP',quality=84,method=5)
def std(im):return max(ImageStat.Stat(im.resize((96,64))).stddev)
async def one(browser,sid,url):
 page=await browser.new_page(viewport={'width':1440,'height':920},device_scale_factor=1,locale='en-US',color_scheme='light')
 try:
  r=await page.goto(url,wait_until='domcontentloaded',timeout=25000)
  if not r or r.status>=400:raise ValueError('HTTP '+str(r.status if r else None))
  await page.wait_for_timeout(1400)
  clicked=await click_consent(page)
  if not clicked:
   labels=[x.strip()[:60] for x in await page.locator('button').all_text_contents()]
   print('NO_CONSENT_FOUND',sid,labels[-18:],flush=True)
   return {'id':sid,'status':'not changed','reason':'No supported consent control visible'}
  await page.keyboard.press('Escape')
  await page.mouse.move(1410,895)
  im=await snap(page,0)
  detail=await snap(page,850)
  diff=max(ImageStat.Stat(ImageChops.difference(im.resize((96,64)),detail.resize((96,64)))).mean)
  if std(im)<13 or std(detail)<11 or diff<8:
   raise ValueError('Unusable image after consent')
  for folder,name,img in [
   ('sites',sid+'.webp',im),
   ('notes',sid+'-hero.webp',im),
   ('notes',sid+'-detail.webp',detail),
   ('modules',sid+'-hero.webp',im.crop((0,95,1440,850))),
   ('modules',sid+'-detail.webp',detail.crop((0,95,1440,850)))]:
    path=SHOTS/folder/name
    if not path.exists():raise ValueError('Missing original canonical image '+str(path))
    store(img,path)
  print('RECAPTURE_SUCCESS',sid,clicked,'std',round(std(im),1),flush=True)
  return {'id':sid,'status':'recaptured','consent_action':clicked,'std':round(std(im),1)}
 except Exception as e:
  print('RECAPTURE_SKIPPED',sid,str(e)[:120],flush=True)
  return {'id':sid,'status':'not changed','reason':str(e)[:300]}
 finally:await page.close()
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(headless=True,channel='chrome',args=['--no-sandbox','--disable-dev-shm-usage'])
  result=await asyncio.gather(*(one(b,*row) for row in TARGETS))
  await b.close()
 path=SHOTS/'research-v21'/'recapture-report.json'
 path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print('V21_CONSENT_RECAPTURE',json.dumps(result),flush=True)
if __name__=='__main__':asyncio.run(main())
