import {afterEach,it,expect,vi} from 'vitest';
import {api} from './types';
afterEach(()=>vi.unstubAllGlobals());
it('propagates structured API error codes',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,json:async()=>({error:{code:'rate_limit'}})}));
  await expect(api('tasks')).rejects.toThrow('rate_limit');
});
it('handles no-content deletes',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,status:204}));
  await expect(api('tasks/id','DELETE')).resolves.toBeUndefined();
});
