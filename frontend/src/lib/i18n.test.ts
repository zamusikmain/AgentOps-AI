import {describe,it,expect} from 'vitest';
import {en,ru,translate} from './i18n';
describe('Translations',()=>{
  it('has identical nonempty keys in both languages',()=>{
    expect(Object.keys(ru).sort()).toEqual(Object.keys(en).sort());
    for(const key of Object.keys(en)){
      expect(translate('en',key).length).toBeGreaterThan(0);
      expect(translate('ru',key).length).toBeGreaterThan(0);
    }
  });
  it('never exposes unknown provider error text',()=>{
    expect(translate('ru','secret error contents')).toBe(ru.error);
  });
});
