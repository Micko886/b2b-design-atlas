#!/usr/bin/env python3
"""Quality pass for real, public V1.9 captures. Use normal consent controls, never DOM hiding."""
import asyncio, io, json, re, datetime
from pathlib import Path
from PIL import Image, ImageStat, ImageChops, ImageDraw
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
SHOTS=ROOT/'screenshots'
RESULTS=[]
TARGETS=[
  ('universal-robots','https://www.universal-robots.com/','Use necessary cookies only',0,850),
  ('siemens-healthineers','https://www.siemens-healthineers.com/','Allow necessary only',0,850),
  ('boston-dynamics','https://bostondynamics.com/',None,850,1650),
]
def save(image,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    image.convert('RGB').save(path,'WEBP',quality=84,method=5)
def readable(im):
    v=ImageStat.Stat(im.resize((96,64)).convert('RGB')).stddev
    return max(v)>=12
async def screen(page):
    await page.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i=>i.loading='eager')")
    try:await page.evaluate("document.fonts.ready")
    except Exception:pass
    await page.wait_for_timeout(750)
    data=await page.screenshot(type='png',full_page=False,animations='disabled',timeout=15000)
    return Image.open(io.BytesIO(data)).convert('RGB')
async def do_capture(browser,row):
    sid,url,consent,y1,y2=row
    page=await browser.new_page(viewport={'width':1440,'height':920},device_scale_factor=1,
        locale='en-US',color_scheme='light')
    try:
      response=await page.goto(url,wait_until='domcontentloaded',timeout=30000)
      if not response or response.status>=400:raise RuntimeError('HTTP '+str(response.status if response else 'unknown'))
      await page.wait_for_timeout(1700)
      clicked=False
      if consent:
        for frame in page.frames:
          try:
            btn=frame.get_by_role('button',name=re.compile(re.escape(consent),re.I)).first
            if await btn.count() and await btn.is_visible(timeout=700):
                await btn.click(timeout=3500);clicked=True;break
          except Exception as exc:
            print('button try:',sid,type(exc).__name__,flush=True)
        if not clicked:
          # Some banners use click targets without the button role.
          for frame in page.frames:
            try:
              el=frame.get_by_text(consent,exact=True).first
              if await el.count() and await el.is_visible(timeout=700):
                  await el.click(timeout=3500);clicked=True;break
            except Exception as exc:
              print('text try:',sid,type(exc).__name__,flush=True)
        if not clicked:raise RuntimeError('Consent button could not be used normally: '+consent)
        await page.wait_for_timeout(800)
      await page.evaluate('(y)=>window.scrollTo({top:y,behavior:"instant"})',y1)
      await page.wait_for_timeout(1350)
      hero=await screen(page)
      await page.evaluate('(y)=>window.scrollTo({top:y,behavior:"instant"})',y2)
      await page.wait_for_timeout(1150)
      detail=await screen(page)
      if not readable(hero) or not readable(detail):raise RuntimeError('Blank screenshot')
      diff=ImageStat.Stat(ImageChops.difference(hero.resize((96,64)),detail.resize((96,64)))).mean
      if max(diff)<7:raise RuntimeError('Sections too visually similar')
      save(hero,SHOTS/'sites'/(sid+'.webp'))
      save(hero,SHOTS/'notes'/(sid+'-hero.webp'))
      save(detail,SHOTS/'notes'/(sid+'-detail.webp'))
      save(hero.crop((0,105,1440,790)),SHOTS/'modules'/(sid+'-hero.webp'))
      save(detail.crop((0,90,1440,810)),SHOTS/'modules'/(sid+'-detail.webp'))
      result={'id':sid,'status':'recaptured','url':page.url,'consent_clicked':clicked,
          'first_scroll':y1,'second_scroll':y2,'frame_change':round(max(diff),1)}
      print('RECUT',json.dumps(result),flush=True)
      return result
    finally:await page.close()
async def main():
    async with async_playwright() as p:
      browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
      for row in TARGETS:RESULTS.append(await do_capture(browser,row))
      await browser.close()
    report={'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),'items':RESULTS}
    p=SHOTS/'research-v19'/'recapture-quality.json'
    p.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    audit=json.loads((SHOTS/'research-v19'/'audit.json').read_text())
    approved=audit['approved']
    sheet=Image.new('RGB',(1180,((len(approved)+3)//4)*236+18),'#f5f5f5')
    pen=ImageDraw.Draw(sheet)
    for i,sid in enumerate(approved):
      src=Image.open(SHOTS/'sites'/(sid+'.webp')).convert('RGB')
      src.thumbnail((276,200))
      x=10+(i%4)*294;y=12+(i//4)*236
      sheet.paste(src,(x,y))
      pen.text((x,y+203),sid,fill='#111111')
    sheet.save(SHOTS/'research-v19'/'contact-sheet.jpg',format='JPEG',quality=83,optimize=True)
    print('RECAPTURE_COMPLETE',len(RESULTS),flush=True)
if __name__=='__main__':asyncio.run(main())
