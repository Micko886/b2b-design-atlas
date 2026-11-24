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
("boston-dynamics","Boston Dynamics","Industrial Automation","Mobile industrial robotics","Robotics systems","https://bostondynamics.com/","Mobile robots for industrial inspection, materials handling, and automation.","Use product storytelling and demonstrated real-world applications to clarify novel hardware.","Hero","Robotics-first product introduction","Product footage and technology claims orient industrial buyers.","Applications","Robot use-case discovery","Industrial use cases make emerging robotics easier to evaluate."),
("universal-robots","Universal Robots","Industrial Automation","Collaborative robotic arms","Robotics hardware","https://www.universal-robots.com/","Collaborative robot arms and supporting applications for manufacturing automation.","Lead buyers from a robot family to applications and system integration.","Hero","Collaborative robot proposition","Robot hardware and benefits anchor an applications-first entry.","Applications","Robot deployment use cases","Manufacturing scenarios make automation buying decisions concrete."),
("abb-robotics","ABB Robotics","Industrial Automation","Industrial robots and automation","Automation systems","https://www.abb.com/global/en/areas/robotics","Robot products, automation services and application software.","Provide category clarity across industrial robotics and automation software.","Products","ABB robotics portfolio","Hardware categories and software paths form a multi-product platform.","Capabilities","Robotics solution architecture","Application routes and engineering software extend equipment discovery."),
("beckhoff","Beckhoff","Industrial Automation","PC-based machine control","Industrial automation components","https://www.beckhoff.com/en-us/","Industrial PCs, EtherCAT, control software and motion systems.","Organize highly technical products by system architecture and engineering role.","Products","Control platform product families","Component-oriented navigation supports technical buyers.","Capabilities","Automation platform integration","System-level relationships connect devices and software."),
("omron-automation","OMRON Automation","Industrial Automation","Industrial automation and sensing","Automation systems","https://automation.omron.com/en/us/","Machine automation, sensors, controls and integrated manufacturing solutions.","Balance an extensive product catalog with solution-led exploration.","Products","Automation product navigation","Deep categories help engineers locate precise hardware.","Applications","Industrial automation solutions","Solution paths connect parts to operational problems."),
("rockwell-automation","Rockwell Automation","Industrial Automation","Industrial control systems","Industrial technology platform","https://www.rockwellautomation.com/en-us.html","Industrial automation equipment, software and manufacturing services.","Align hardware, factory software and customer outcomes in one journey.","Hero","Integrated factory technology introduction","Enterprise-scale automation is explained as a unified proposition.","Capabilities","Plant operations and product discovery","Distinct product and service families support multiple industrial buyer roles."),
("cognex","Cognex","Industrial Automation","Machine vision and barcode reading","Industrial sensing","https://www.cognex.com/","Industrial machine vision, AI vision and barcode readers.","Explain technical differentiation using product visuals and application examples.","Products","Machine vision product range","Product-led navigation supports industrial inspection use cases.","Applications","Vision inspection applications","Application examples bridge technology and equipment selection."),
("sick","SICK","Industrial Automation","Industrial sensing","Sensor manufacturer","https://www.sick.com/us/en/","Industrial sensors and safety systems for automation.","Offer a direct path into complex industrial sensor families.","Products","Industrial sensor navigation","Sensor categories support precise engineering lookup.","Applications","Sensing applications","Application selection helps buyers interpret component performance."),
("ifm","ifm","Industrial Automation","Sensors and industrial IO-Link","Industrial automation components","https://www.ifm.com/us/en","Industrial sensors, IO-Link systems and automation software.","Use compact product taxonomy to reduce time-to-specification.","Products","Sensors and IO-Link product catalog","Product grouping reflects procurement and engineering tasks.","Capabilities","Automation system capabilities","Industrial application context helps qualify hardware."),
("te-connectivity","TE Connectivity","Electronics","Industrial connectors and sensors","Component manufacturer","https://www.te.com/en/home.html","Connectors, terminals, sensors and industrial electronics components.","Design dense parts navigation for exact product and specification discovery.","Products","Connectivity component directory","Hierarchical taxonomy supports repeated technical searches.","Applications","Industrial connectivity scenarios","Application contexts organize a large component portfolio."),
("phoenix-contact","Phoenix Contact","Electronics","Industrial connectivity and control","Electronic and automation components","https://www.phoenixcontact.com/en-us/","Industrial connectors, control cabinet products and automation systems.","Combine product finding, configuration, and solution expertise.","Products","Industrial connection products","Structured category navigation supports component sourcing.","Capabilities","Custom product and system solutions","The product system connects standard parts with engineering services."),
("harting","HARTING","Electronics","Industrial connectors","Connectivity components","https://www.harting.com/US/en-us","Industrial electrical, data and power connectivity products.","Turn numerous connector families into a navigable technical library.","Products","Industrial connectivity taxonomy","Structured families serve precise component research.","Applications","Connector use-case support","Industrial environments give product requirements context."),
("analog-devices","Analog Devices","Electronics","Analog signal processing","Semiconductor manufacturer","https://www.analog.com/en/index.html","Analog and mixed-signal semiconductors with engineer-oriented knowledge.","Prioritize technical search, documentation, and application content.","Products","Semiconductor products","Engineer-facing taxonomy connects parts to technical needs.","Resources","Design resources and technical content","Deep learning content reduces the burden of component selection."),
("jabil","Jabil","Electronics","Product design and manufacturing","Electronics manufacturing services","https://www.jabil.com/","Engineering and advanced manufacturing services for global hardware businesses.","Make large manufacturing capabilities feel like a coherent service offering.","Hero","Global manufacturing proposition","Position engineering and production scale together.","Capabilities","Manufacturing service breadth","Capability navigation communicates how complex products get built."),
("flex-manufacturing","Flex","Electronics","Integrated manufacturing and supply chain","Manufacturing services","https://flex.com/","Product design, engineering, production and supply chain services.","Tell a cross-industry engineering-to-delivery story without overwhelming buyers.","Hero","Engineering and manufacturing introduction","A large manufacturing business becomes understandable through outcomes.","Process","Design-to-delivery workflow","Service stages support a multi-discipline procurement journey."),
("wurth-elektronik","Würth Elektronik","Electronics","Electronic and electromechanical components","Electronic components","https://www.we-online.com/en/","Electronic and electromechanical components with technical selection resources.","Use category architecture to support engineering component procurement.","Products","Electronic component families","Catalog-led discovery supports exact product selection.","Resources","Design-in technical guidance","Technical resources help validate component decisions."),
("covestro","Covestro","Materials","Polymer materials and applications","Materials science supplier","https://www.covestro.com/en","Polymer and high-performance materials for industrial applications.","Lead from industry use cases into material selection and innovation evidence.","Hero","Materials innovation proposition","High-performance materials are introduced through applications.","Products","Material portfolio entry","Technical materials need a clear category route."),
("eastman","Eastman","Materials","Specialty materials innovation","Chemical materials manufacturer","https://www.eastman.com/en","Specialty materials, performance chemicals and manufacturing applications.","Connect material properties to buyer outcomes, brands and application sectors.","Hero","Material innovation narrative","Applications position an otherwise complex portfolio.","Products","Specialty material product discovery","Product taxonomy supports application-specific sourcing."),
("corning","Corning","Materials","Specialty glass and materials science","Advanced materials manufacturer","https://www.corning.com/worldwide/en.html","Specialty glass, ceramics, optical communications and life sciences.","Show varied advanced-material capabilities without losing brand coherence.","Hero","Materials science authority","The site links corporate innovation with concrete applications.","Applications","Cross-industry materials portfolio","Application routes demonstrate breadth without relying on slogans."),
("dupont","DuPont","Materials","Advanced industrial materials","Specialty materials","https://www.dupont.com/","Materials science and specialty products for industrial markets.","Balance industries, product discovery and technical innovation.","Hero","Science and industrial applications","Applications explain why technical material capabilities matter.","Products","Technical material discovery","Material families guide sourcing and engineering evaluation."),
("saint-gobain","Saint-Gobain","Materials","Construction and industrial materials","Industrial materials supplier","https://www.saint-gobain.com/en","Materials and systems for construction, infrastructure and industry.","Build a clear multi-market story across materials and built environment.","Hero","Materials and sustainability narrative","Market relevance organizes a broad materials business.","Projects","Applications and project evidence","Built-environment outcomes demonstrate product utility."),
("ge-healthcare","GE HealthCare","Medical Technology","Clinical imaging and devices","Medical equipment manufacturing","https://www.gehealthcare.com/","Medical imaging and healthcare technology for clinical enterprises.","Present clinically complex products with clear modality paths.","Products","Clinical imaging equipment categories","Large equipment ranges require disciplined information grouping.","Capabilities","Healthcare technology platform","Clinical workflows provide context for hardware procurement."),
("siemens-healthineers","Siemens Healthineers","Medical Technology","Medical imaging and diagnostics","Healthcare equipment and diagnostics","https://www.siemens-healthineers.com/","Medical imaging, diagnostics and healthcare enterprise services.","Separate medical modalities and enterprise workflows with clinical clarity.","Hero","Healthcare technology proposition","The opening explains technical innovation through clinical value.","Products","Medical diagnostic systems","Modality-first organization supports specialist research."),
("medtronic","Medtronic","Medical Technology","Medical technology systems","Medical device manufacturer","https://www.medtronic.com/us-en/index.html","Medical devices, clinical specialty solutions and professional resources.","Support distinct provider audiences and device selection.","Hero","Medical technology introduction","Clinical themes guide a broad device company.","Products","Medical device category hierarchy","Specialties help clinicians reach relevant products."),
("agilent","Agilent","Lab Technology","Lab instruments and analytical chemistry","Laboratory equipment","https://www.agilent.com/","Laboratory instruments and services for analytical and life-science labs.","Make technical instrumentation searchable by lab workflow.","Products","Laboratory instrument finder","Product navigation supports precise technical evaluation.","Applications","Laboratory methods and workflows","Method-level guidance connects equipment to research needs."),
("waters","Waters","Lab Technology","Analytical instruments","Laboratory technology","https://www.waters.com/","Analytical laboratory instruments and scientific workflows.","Organize laboratory products around the experiments they enable.","Hero","Analytical science proposition","Technical benefit is introduced through laboratory impact.","Products","Instrument family discovery","Instrument categories reduce product research friction."),
("ge-vernova","GE Vernova","Energy","Power and grid technology","Energy systems manufacturer","https://www.gevernova.com/","Power generation, electrification, wind and grid infrastructure technology.","Separate massive industrial business units with a coherent navigation layer.","Hero","Energy transition and power technologies","Infrastructure-scale technology is positioned through outcomes.","Capabilities","Energy technology portfolio","Industrial energy offerings are grouped by application."),
("schneider-electric","Schneider Electric","Energy","Electrical automation and energy management","Electrification technology","https://www.se.com/us/en/","Electrical distribution, energy management and industrial automation.","Combine commerce-focused product discovery with solution navigation.","Products","Electrical product categories","Business and engineering users can find exact device families.","Capabilities","Energy management solutions","Solution framing complements a large product catalog."),
("hitachi-energy","Hitachi Energy","Energy","Grid technology and transformers","Power infrastructure supplier","https://www.hitachienergy.com/","Grid equipment, HVDC, transformers and power systems.","Communicate technical infrastructure outcomes with project proof.","Hero","Power grid technology entry","Industrial systems are contextualized with the energy transition.","Projects","Grid infrastructure use cases","System projects reinforce credibility beyond catalogs."),
("vestas","Vestas","Energy","Wind turbine platforms","Renewable energy equipment","https://www.vestas.com/en","Wind turbine manufacturing and related service solutions.","Present large physical products through visual proof and product architecture.","Hero","Wind technology storytelling","Large-scale hardware imagery makes the offering tangible.","Products","Wind turbine portfolio","Product series and service benefits guide technical buyers."),
("fluence-energy","Fluence","Energy","Grid-scale battery energy storage","Energy storage systems","https://fluenceenergy.com/","Grid-scale energy storage, software and managed operations.","Differentiate hardware, service and software in one energy system.","Hero","Energy storage proposition","Infrastructure outcomes introduce the platform.","Capabilities","Storage product and software system","Integrated energy technology is presented in workable components."),
("onshape","Onshape","Enterprise Software","Cloud-native product design software","Engineering CAD SaaS","https://www.onshape.com/en/","Cloud CAD, product data and engineering collaboration.","Explain collaboration benefits through concrete product UI and engineering jobs.","Hero","Cloud CAD engineering platform","Product-led storytelling ties the software to team workflows.","Capabilities","Product development workflows","Collaboration and version control become buying criteria."),
("celonis","Celonis","Enterprise Software","Process intelligence and mining","Enterprise process software","https://www.celonis.com/","Process intelligence platform for operational optimization.","Show an abstract enterprise platform through outcomes and real interfaces.","Hero","Process intelligence proposition","Operational impact leads complex software messaging.","Capabilities","Business process use cases","Enterprise application scenarios clarify value."),
("datadog","Datadog","Enterprise Software","Observability and application security","Developer SaaS","https://www.datadoghq.com/","Cloud observability, infrastructure monitoring and application security.","Make a broad technical platform navigable without diluting key products.","Hero","Platform visibility proposition","Product UI demonstrates an otherwise abstract technical benefit.","Products","Observability modules","Product-family navigation helps technical buyers evaluate scope."),
("servicenow","ServiceNow","Enterprise Software","Enterprise workflow automation","Enterprise software platform","https://www.servicenow.com/","Enterprise workflow, IT operations and business process automation.","Use cross-functional business outcomes to organize a giant SaaS portfolio.","Hero","Workflow automation introduction","Enterprise productivity benefits make the platform concrete.","Capabilities","Business workflow solution paths","Audience-oriented solutions support multiple departments."),
("hilti","Hilti","Industrial Distribution","Professional tools and construction technology","Construction equipment","https://www.hilti.com/","Professional power tools, industrial fastening and field services.","Combine product catalog commerce with contractor service relationships.","Products","Professional equipment catalog","Tool categories support jobsite-oriented buying decisions.","Capabilities","Construction service offering","Products and services form one practical workflow."),
("mcmaster-carr","McMaster-Carr","Industrial Distribution","Industrial supplies catalog","Industrial parts ecommerce","https://www.mcmaster.com/","Technical industrial components and MRO procurement catalog.","Study extreme search-first, specification-heavy industrial product UX.","Products","Industrial catalog navigation","Procurement speed takes priority over decorative marketing.","Resources","Specification-first buying path","Dense technical discovery serves expert repeat buyers."),
("danfoss","Danfoss","Industrial Technology","Drives, controls and energy efficiency","Industrial engineering equipment","https://www.danfoss.com/en/","Drives, cooling, hydraulics and power electronics.","Unify industrial equipment families under coherent application routes.","Hero","Industrial engineering proposition","Market challenges contextualize technical products.","Products","Industrial product discovery","Equipment pathways bridge applications and engineering specifications.")
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
    if len(sites)<12:raise SystemExit('Too few approved captures for V1.9; do not publish.')
if __name__=='__main__':asyncio.run(main())
