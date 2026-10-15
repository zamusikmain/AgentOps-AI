import {describe,it,expect} from 'vitest';
import {smokeStrings} from './live-smoke-i18n';
describe('live smoke localization',()=>{it('keeps RU/EN complete and distinct with explicit offline provenance',()=>{expect(Object.keys(smokeStrings.ru).sort()).toEqual(Object.keys(smokeStrings.en).sort());expect(smokeStrings.en.notice).toContain('blocked');expect(smokeStrings.ru.notice).toContain('заблокированы');expect(smokeStrings.en.comparison).toContain('NOT VERIFIED');expect(smokeStrings.ru.save).toContain('ручную');});});
