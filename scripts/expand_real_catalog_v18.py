#!/usr/bin/env python3
"""Curated Atlas V1.8 catalog expansion. Capture real pages, never synthesize visuals.

Run from extracted source with the repo's tracked screenshots folder present.
Only browser-verified successful captures enter source_index.json.
"""
from __future__ import annotations
import asyncio, datetime, io, json, re, shutil
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageStat, ImageChops
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
SCREENS=ROOT/'screenshots'
OUT=SCREENS/'research-v18'
AUDIT=[]
STAMP=datetime.datetime.now(datetime.timezone.utc).isoformat()
# Company, sector, specific visual learning objective; actual source URLs vetted separately.
# Each site has independent editorial notes for its opening section and its real below-fold region.
CANDIDATES=[
  ("oshcut","OSH Cut","Manufacturing","Instant metal-part quoting","Quote-first machining","https://www.oshcut.com/","CAD upload, pricing and manufacturing capabilities are connected to an early buyer action.","Make the immediate quoting route visible without hiding capabilities.","RFQ","Instant-pricing entry point","A direct pricing path is supported by manufacturing specificity.","Capabilities","Manufacturing proof and process","The page explains why an instant-quote service is credible."),
  ("fathom","Fathom","Manufacturing","Advanced production capabilities","Digital manufacturing","https://fathommfg.com/","A multi-process manufacturing supplier covering prototypes through industrial production.","Turn a wide service catalog into a findable buying path.","Capabilities","Advanced manufacturing offer","A broad capability set is introduced without losing the path to request work.","Products","Manufacturing capability discovery","Multiple manufacturing processes are connected to buyer needs."),
  ("materialise","Materialise","Manufacturing","Industrial additive manufacturing","3D printing platforms","https://www.materialise.com/en","Industrial manufacturing, software, and healthcare audiences receive distinct paths.","Separate complex B2B audience needs before deep technical exploration.","Hero","Audience-led opening","The entry narrative introduces an industrial technology portfolio.","Capabilities","Industrial versus healthcare paths","Multiple audiences are organized without mixing product use cases."),
  ("weerg","Weerg","Manufacturing","3D printing and CNC","On-demand manufacturing","https://www.weerg.com/","Online manufacturing with a material-led service navigation and an order path.","Expose materials and services without burying the conversion path.","Hero","Online manufacturing entry","Production processes and the next buying step are introduced together.","Products","Material and process navigation","Materials and manufacturing methods help buyers shortlist quickly."),
  ("stratasys","Stratasys","Industrial Technology","Industrial 3D printers","Additive manufacturing hardware","https://www.stratasys.com/en/","Industrial 3D printer portfolio with application and material pathways.","Make complex hardware easy to enter by industry or production use case.","Hero","Industrial printing proposition","Use-case-led technology presentation gives context before product details.","Products","Printer family navigation","The hardware portfolio supports comparison across technologies."),
  ("nordicsemi","Nordic Semiconductor","Industrial Technology","Wireless semiconductor solutions","Electronics and IoT","https://www.nordicsemi.com/","Wireless components, developer resources, and IoT applications for engineering teams.","Balance product releases with technical developer entry points.","Hero","Developer-oriented technology entry","A technical audience is given product and learning pathways.","Products","Component family discovery","Product categories reduce research effort for hardware teams."),
  ("sgw-designworks","SGW Designworks","Product Design","Engineering to production","Product development services","https://www.sgwdesignworks.com/","Product development combines design, engineering, prototyping and manufacturing preparation.","Show the delivery chain rather than only a list of specialties.","Hero","Integrated product design pitch","Explains the overlap of engineering and manufacturing readiness.","Process","End-to-end service narrative","Linked disciplines make the scope of engagement easier to judge."),
  ("design1st","Design 1st","Product Design","Product design to delivery","Industrial product development","https://design1st.com/","Product strategy, industrial design, electronics and mechanical engineering under one service system.","Translate a large service tree into buyer-oriented navigation.","Capabilities","Design and engineering architecture","An extensive interdisciplinary offer becomes navigable.","Process","Product development stages","Design, engineering and delivery reinforce the end-to-end proposition."),
  ("219-design","219 Design","Product Design","Integrated engineering teams","Hardware product development","https://219design.com/","Mechanical, electrical and software engineering supporting product development.","Lead with an engineering promise and substantiate it with project capability.","Hero","Engineering credibility opening","Capability messaging is anchored by a distinct technical positioning.","Capabilities","Cross-discipline engineering","Mechanical, electrical and software disciplines remain discoverable."),
  ("studiored","StudioRed","Product Design","Product design and engineering","Product innovation consulting","https://www.studiored.com/","Design, engineering, UX and prototyping presented as complementary practices.","Connect creative case studies with technical delivery proof.","Hero","Product innovation positioning","Visual work is connected to engineering services.","Projects","Case-study-first portfolio","Project proof helps qualify the consulting relationship."),
  ("ideo","IDEO","Product Design","Human-centered design","Design consultancy","https://www.ideo.com/","Design-led innovation, business transformation and featured project evidence.","Use typography and cases to explain an abstract consulting proposition.","Hero","Expressive consulting intro","Type hierarchy establishes a memorable value proposition.","Projects","Case-study storytelling","Client work translates abstract expertise into tangible outcomes."),
  ("arup","Arup","Engineering","Engineering and built environment","Consulting engineering","https://www.arup.com/","Engineering services connected to projects, markets and research.","Build credibility through markets and verified project evidence.","Hero","Engineering-led positioning","Services and purpose set up the consultancy's expertise.","Projects","Global engineering proof","Project work and sector expertise reinforce credibility."),
  ("ptc","PTC","Enterprise Software","Industrial product lifecycle software","Enterprise engineering SaaS","https://www.ptc.com/en","Product data, PLM and connected engineering tools for enterprise manufacturers.","Keep complex enterprise software legible through workflow framing.","Hero","Connected engineering promise","A technical proposition is framed as an operational outcome.","Products","Industrial software architecture","Product routes turn enterprise complexity into a usable taxonomy."),
  ("flexport","Flexport","Logistics","Global freight and trade platform","Digital freight forwarding","https://www.flexport.com/","Shipping, customs and supply-chain software in one B2B service interface.","Balance operational utility with a clear enterprise conversion path.","Hero","Global trade platform intro","A broad logistics platform is introduced through buyer outcomes.","Capabilities","Service and platform architecture","Freight services and software functions stay distinguishable."),
  ("project44","project44","Logistics","Supply chain intelligence","Enterprise logistics software","https://www.project44.com/","Shipment visibility, transportation, yard and analytics products under a common platform.","Present enterprise modules through clear buyer jobs and entry points.","Hero","Supply chain intelligence hero","Operational intelligence is connected to practical buying goals.","Products","Platform modules","Complex logistics features are grouped in understandable routes."),
  ("fourkites","FourKites","Logistics","Autonomous supply chain execution","Logistics automation software","https://www.fourkites.ai/","AI-enabled exception handling, visibility, and execution outcomes in logistics.","Distinguish platform promise, evidence and quantified outcomes.","Hero","Outcome-led enterprise messaging","Operational value takes priority over a generic feature list.","Trust","Results and platform proof","Numerical outcomes support enterprise credibility."),
  ("freightos","Freightos","Logistics","Freight booking marketplace","Logistics marketplace","https://www.freightos.com/","Digital freight rate comparison and purchasing tools for shippers and forwarders.","Orient multiple user types before asking them to book freight.","Hero","Freight buying entry point","A clear marketplace proposition gives the visitor a fast path.","Process","Freight marketplace journey","Rate discovery and booking form a coherent buyer sequence."),
  ("shipbob","ShipBob","Logistics","Ecommerce fulfillment solutions","Third-party logistics","https://www.shipbob.com/","Fulfillment services, integrations, case studies, and quote entry points.","Communicate operational scope before conversion.","Hero","Fulfillment offer","The value proposition positions logistics as a growth enabler.","Trust","Fulfillment network proof","Operational scale and cases support a B2B buying decision."),
  ("quickparts","Quickparts","Manufacturing","Prototyping to production","On-demand production","https://quickparts.com/","CNC, additive processes and production sourcing with two quote pathways.","Split rapid prototyping RFQ from high-volume production inquiries.","RFQ","Two-track quote architecture","Prototyping and production visitors get separate next steps.","Products","Process selection menu","Technology offerings support findability across manufacturing needs."),
  ("keyence","KEYENCE","Industrial Technology","Industrial sensing and vision","Industrial components distribution","https://www.keyence.com/","Engineering products organized as deep technical categories and solutions.","Design for repeat buyers who need highly specific product navigation.","Products","Industrial product taxonomy","Dense technical categories are prioritized for engineered-component lookup.","Capabilities","Application discovery","Product category depth supports complex procurement research."),
  ("hatch","Hatch","Engineering","Engineering and project implementation","Engineering consultancy","https://www.hatch.com/","Engineering, energy and infrastructure project implementation with issue-based messaging.","Show industry relevance through varied project narratives.","Hero","Engineering outlook and projects","Project-led storytelling connects technical expertise with outcomes.","Projects","Industry and project narrative","Proof is anchored in engineering delivery examples."),
  ("3dsystems","3D Systems","Industrial Technology","Additive manufacturing systems","3D printers and materials","https://www.3dsystems.com/","Industrial 3D printers, material systems and industry use cases.","Help engineers navigate from manufacturing use cases into hardware.","Hero","Additive systems positioning","Technical audiences can enter through outcomes and applications.","Products","Technology family navigation","Hardware and use cases form a navigable system."),
]
CHALLENGE=re.compile(r'access denied|just a moment|checking your browser|robot check|verify you are human|enable javascript|captcha|forbidden|please enable cookies',re.I)
COOKIE=[
  re.compile(r'^(reject (all|optional)|decline (all|optional)|necessary only|only necessary|essential only)$',re.I),
  re.compile(r'^(accept all|allow all|accept cookies|accept all cookies|accept|agree|got it|ok)$',re.I)
]
def rms(image):
    im=image.resize((96,64)).convert('RGB')
    st=ImageStat.Stat(im)
    return max(st.stddev)
def save_img(image,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    image.convert('RGB').save(path,'WEBP',quality=83,method=5)
def mk_meta(row):
    (ident,name,sector,focus,model,url,summary,takeaway,*_)=row
    return dict(id=ident,name=name,sector=sector,focus=focus,model=model,
        url=url,domain=urlparse(url).hostname.removeprefix('www.'),
        summary=summary,takeaway=takeaway,palette='neutral',featured=False)

async def dismiss(page):
    try:
      for _ in range(2):
        for frame in page.frames:
          for pattern in COOKIE:
            try:
              button=frame.get_by_role('button',name=pattern).first
              if await button.count() and await button.is_visible(timeout=700):
                await button.click(timeout=1700);await page.wait_for_timeout(300);return
            except Exception:pass
        await page.wait_for_timeout(450)
    except Exception:pass

async def screenshot(page):
    await page.evaluate("""async()=>{document.querySelectorAll('img[loading="lazy"]').forEach(x=>x.loading='eager');try{await document.fonts.ready}catch(e){}}""")
    await page.wait_for_timeout(650)
    return Image.open(io.BytesIO(await page.screenshot(type='png',full_page=False,animations='disabled',timeout=12000))).convert('RGB')

async def capture_one(browser,sem,row):
    ident=row[0];url=row[5]
    async with sem:
      page=await browser.new_page(viewport={'width':1440,'height':920},
          device_scale_factor=1,locale='en-US',color_scheme='light')
      try:
        resp=await page.goto(url,wait_until='domcontentloaded',timeout=26000)
        if not resp or resp.status>=400:raise RuntimeError('HTTP '+str(resp.status if resp else 'no response'))
        await page.wait_for_timeout(1100)
        title=(await page.title())[:140]
        body=(await page.locator('body').inner_text(timeout=5000))[:2500]
        if CHALLENGE.search(title+' '+body[:450]):raise RuntimeError('Bot challenge / access denied')
        if len(body.strip())<110:raise RuntimeError('Too little visible text for a quality design reference')
        await dismiss(page)
        top=await screenshot(page)
        if rms(top)<12:raise RuntimeError('Blank or low-information opening screenshot')
        source_file=SCREENS/'sites'/(ident+'.webp')
        save_img(top,source_file)
        approved=[dict(id=ident,kind='website',url=url,resolved_url=page.url,title=title,status='captured',image_file=str(source_file.relative_to(ROOT)),contrast=round(rms(top),1))]
        # A note is a genuine crop of a browser screenshot; no generated mockup.
        notes=[];mods=[]
        for suffix,category,section_title,lesson,y0,y1 in [('hero',row[8],row[9],row[10],105,790)]:
          nid=ident+'-'+suffix
          path=SCREENS/'notes'/(nid+'.webp')
          save_img(top,path)
          notes.append(dict(id=nid,site_id=ident,type=category,title=section_title,
             pattern=category+' study',url=url,summary=row[6],lesson=lesson))
          crop=top.crop((0,y0,1440,y1))
          cid=nid
          dest=SCREENS/'modules'/(cid+'.webp')
          save_img(crop,dest)
          mods.append(dict(id=cid,site_id=ident,page_id=nid,
            category=category,type=category,title=section_title,
            lesson=lesson,summary=row[6],url=url,
            source_capture='/screenshots/notes/'+nid+'.webp',
            image_file=cid+'.webp',crop_px=[0,y0,1440,y1],
            reference_type='Real website — browser crop'))
        # Capture an actual below-fold segment only if a sufficiently long, changed page exists.
        height=await page.evaluate('document.documentElement.scrollHeight')
        if height>1520:
          await page.evaluate('window.scrollTo({top:850,behavior:"instant"})')
          await page.wait_for_timeout(900)
          lower=await screenshot(page)
          delta=ImageStat.Stat(ImageChops.difference(top.resize((96,64)),lower.resize((96,64)))).mean
          if rms(lower)>=11 and max(delta)>9:
            suffix='detail';nid=ident+'-'+suffix
            dest=SCREENS/'notes'/(nid+'.webp')
            save_img(lower,dest)
            notes.append(dict(id=nid,site_id=ident,type=row[11],title=row[12],
                pattern=row[11]+' study',url=url,summary=row[6],lesson=row[13]))
            y0,y1=90,810
            crop=lower.crop((0,y0,1440,y1))
            save_img(crop,SCREENS/'modules'/(nid+'.webp'))
            mods.append(dict(id=nid,site_id=ident,page_id=nid,
                category=row[11],type=row[11],title=row[12],
                lesson=row[13],summary=row[6],url=url,
                source_capture='/screenshots/notes/'+nid+'.webp',
                image_file=nid+'.webp',crop_px=[0,y0,1440,y1],
                reference_type='Real website — browser crop'))
            approved.append(dict(id=nid,kind='below-fold section',status='captured',scroll=850,pixel_difference=round(max(delta),1)))
        print('CAPTURED',ident,'sections',len(mods),'title',title[:60],flush=True)
        return (mk_meta(row),notes,mods,approved)
      except Exception as e:
        print('REJECTED',ident,str(e)[:140],flush=True)
        return (None,[],[],[dict(id=ident,status='rejected',url=url,reason=str(e)[:180])])
      finally:
        await page.close()

async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    catalog_path=ROOT/'app/source_index.json'
    module_path=ROOT/'app/module_catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    existing={x['id'] for x in catalog['sites']}
    candidates=[r for r in CANDIDATES if r[0] not in existing]
    async with async_playwright() as p:
      browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
      sem=asyncio.Semaphore(3)
      results=await asyncio.gather(*(capture_one(browser,sem,row) for row in candidates))
      await browser.close()
    sites=[x[0] for x in results if x[0]]
    notes=[n for x in results for n in x[1]]
    mods=[m for x in results for m in x[2]]
    audit=[a for x in results for a in x[3]]
    catalog['sites'].extend(sites);catalog['notes'].extend(notes)
    catalog['checked_at']=STAMP[:10]
    previous=json.loads(module_path.read_text(encoding='utf-8'))
    slugs={x['id'] for x in previous}
    previous.extend(x for x in mods if x['id'] not in slugs)
    catalog_path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    module_path.write_text(json.dumps(previous,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report=dict(created_at=STAMP,attempted=len(candidates),accepted=len(sites),rejected=len(candidates)-len(sites),
       new_notes=len(notes),new_modules=len(mods),total_sites=len(catalog['sites']),
       total_modules=len(previous),approved=[x['id'] for x in sites],results=audit)
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Produce a small review contact sheet, showing genuine captures only.
    if sites:
      from PIL import ImageDraw
      W=1180;thumb=(276,200);cols=4;rows=(len(sites)+3)//4
      sheet=Image.new('RGB',(W,rows*236+18),'#f5f5f5')
      draw=ImageDraw.Draw(sheet)
      for i,entry in enumerate(sites):
        src=Image.open(SCREENS/'sites'/(entry['id']+'.webp')).convert('RGB')
        src.thumbnail(thumb)
        x=10+(i%cols)*294;y=12+(i//cols)*236
        sheet.paste(src,(x,y))
        draw.text((x,y+203),entry['name'],fill='#111111')
      sheet.save(OUT/'contact-sheet.jpg',format='JPEG',quality=81,optimize=True)
    print('REPORT',json.dumps({k:report[k] for k in ['attempted','accepted','rejected','new_notes','new_modules','total_sites','total_modules','approved']},ensure_ascii=False),flush=True)
    # Require meaningful growth; reject a broken batch rather than silently publish 1 or 2.
    if len(sites)<8:raise SystemExit('Too few approved captures; no deployment bundle should be published.')
if __name__=='__main__':asyncio.run(main())
