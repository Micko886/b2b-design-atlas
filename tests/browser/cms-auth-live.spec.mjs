import {test, expect} from '@playwright/test';

// Only a disposable localhost Docker server may be used.
const origin=process.env.CMS_E2E_URL || 'http://localhost:8765';
if(origin!=='http://localhost:8765')throw Error('Refusing non-local test server');
const pass=process.env.QA_OWNER_PASS;

test('V54.5 browser login, CMS access and editor/reviewer release',async({browser})=>{
 test.setTimeout(150000);
 if(!pass)throw Error('Missing temporary QA password');
 const contexts=[];
 const make=async()=>{const c=await browser.newContext({baseURL:origin});contexts.push(c);return c;};
 try{
  const guest=await make(),g=await guest.newPage();
  await g.goto('/admin/content');
  await expect(g).toHaveURL(/\/login\?next=/);
  expect((await guest.request.get('/api/admin/content?kind=site')).status()).toBe(401);

  const owner=await make(),op=await owner.newPage();
  await op.goto('/login?next=%2Fadmin%2Fcontent');
  await op.locator('#auth-form [name=email]').fill('owner-v545@example.test');
  await op.locator('#auth-form [name=password]').fill(pass);
  await op.locator('#auth-form button[type=submit]').click();
  await expect(op).toHaveURL(/\/admin\/content/,{timeout:20000});
  await expect(op.locator('#cms-new')).toBeVisible();
  const ownerMe=await (await owner.request.get('/api/auth/me')).json();
  expect(ownerMe.authenticated).toBe(true);

  async function register(label){
   const c=await make(),page=await c.newPage();
   await page.goto('/register');
   await page.locator('#auth-form [name=email]').fill(label+'-v545@example.test');
   await page.locator('#auth-form [name=display_name]').fill('QA '+label);
   await page.locator('#auth-form [name=password]').fill(pass);
   await page.locator('#auth-form button[type=submit]').click();
   await expect.poll(async()=> (await (await c.request.get('/api/auth/me')).json()).authenticated,{timeout:20000}).toBe(true);
   const me=await (await c.request.get('/api/auth/me')).json();
   return {c,page,me};
  }
  const editor=await register('editor'), reviewer=await register('reviewer'),ordinary=await register('reader');
  for(const [user,role] of [[editor,'editor'],[reviewer,'reviewer']]){
   const res=await owner.request.put('/api/admin/team/role',{
    data:{user_id:user.me.user.id,role},headers:{'x-csrf-token':ownerMe.csrf_token}
   });
   expect(res.status(),await res.text()).toBe(200);
  }
  expect((await ordinary.c.request.get('/admin/content',{maxRedirects:0})).status()).toBe(403);

  const slug='qa-browser-release-545';
  await editor.page.goto('/admin/content?kind=site');
  await expect(editor.page.locator('#cms-new')).toBeVisible();
  await editor.page.locator('#cms-new').click();
  await editor.page.locator('#cms-create-slug').fill(slug);
  const f=editor.page.locator('#cms-create-fields');
  await f.locator('[name=name]').fill('QA browser study');
  await f.locator('[name=url]').fill('https://example.org');
  await f.locator('[name=sector]').fill('Industrial');
  await f.locator('[name=summary]').fill('Private draft');
  await editor.page.locator('#cms-create-form button[type=submit]').click();
  await expect(editor.page.locator('.cms-easy-header-side .cms-item-state')).toContainText('草稿',{timeout:12000});
  const privateList=await (await guest.request.get('/api/source-library')).json();
  expect(privateList.sites.some(x=>x.id===slug)).toBe(false);
  await editor.page.locator('[data-editor-submit]').click();
  await expect(editor.page.locator('.cms-easy-header-side .cms-item-state')).toContainText('待审核');
  await reviewer.page.goto('/admin/content?kind=site&edit='+slug);
  await expect(reviewer.page.locator('[data-transition=reject]')).toBeVisible();
  await expect(reviewer.page.locator('[data-editor-save]')).toHaveCount(0);
  await reviewer.page.locator('[data-transition=reject]').click();
  await expect(reviewer.page.locator('#cms-transition-feedback')).toContainText('退回原因至少 4 个字符');
  await reviewer.page.locator('#cms-review-reason').fill('请完善网站采购路径的分析');
  await reviewer.page.locator('[data-transition=reject]').click();
  await expect(reviewer.page.locator('.cms-easy-header-side .cms-item-state')).toContainText('草稿');
  await editor.page.reload();
  await editor.page.locator('#field-summary').fill('Approved buyer journey.');
  await expect(editor.page.locator('#cms-autosave-status')).toContainText('草稿已保存',{timeout:15000});
  await editor.page.locator('[data-editor-submit]').click();
  await expect(editor.page.locator('.cms-easy-header-side .cms-item-state')).toContainText('待审核');
  await reviewer.page.reload();
  await reviewer.page.locator('[data-transition=publish]').click();
  await expect(reviewer.page.locator('.cms-easy-header-side .cms-item-state')).toContainText('已发布',{timeout:12000});
  const publicList=await (await guest.request.get('/api/source-library')).json();
  expect(publicList.sites.find(x=>x.id===slug)?.summary).toBe('Approved buyer journey.');
 }finally{for(const c of contexts)await c.close();}
});
