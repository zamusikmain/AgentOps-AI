import {describe,it,expect} from 'vitest';
import {liveCopy,modeStatus} from './live-v12';
describe('v12 execution provenance',()=>{
 it('keeps offline and dry modes distinct',()=>{expect(modeStatus('MOCK_ONLY',false)).toBe('MOCK');expect(modeStatus('REAL_DRY_RUN',false)).toBe('DRY RUN');});
 it('requires authorization before live readiness',()=>{expect(modeStatus('REAL_EXECUTION',false)).toBe('LIVE BLOCKED');expect(modeStatus('REAL_EXECUTION',true)).toBe('LIVE READY');expect(modeStatus('REAL_EXECUTION',true,true)).toBe('LIVE RUNNING');expect(modeStatus('REAL_EXECUTION',true,false,true)).toBe('LIVE FAILED');});
 it('localizes every new control and explains cost uncertainty',()=>{expect(Object.keys(liveCopy.ru).sort()).toEqual(Object.keys(liveCopy.en).sort());expect(liveCopy.en.actual).toContain('unknown');expect(liveCopy.ru.notice).toContain('не является разрешением');expect(liveCopy.en.notice).toContain('disabled by default');});
});
