import {describe,it,expect} from 'vitest';
import {authEn,authRu} from './auth-i18n';
describe('authentication localization',()=>{it('has complete RU/EN strings and neutral failures',()=>{expect(Object.keys(authEn).sort()).toEqual(Object.keys(authRu).sort());expect(authEn.invalid_credentials).toBe(authEn.authInvalid);expect(authRu.invalid_credentials).toBe(authRu.authInvalid);expect(authRu.authExpired).toContain('снова');});});
