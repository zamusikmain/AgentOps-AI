import {describe,it,expect} from 'vitest';
import {evidenceEn,evidenceRu} from './evidence-i18n';
import {translate} from './i18n';
import {parseRag} from './knowledge';
describe('Evidence reliability',()=>{
 it('localizes every new metric and evidence status',()=>{expect(Object.keys(evidenceEn).sort()).toEqual(Object.keys(evidenceRu).sort());for(const key of Object.keys(evidenceEn)){expect(translate('en',key)).not.toBe(key);expect(translate('ru',key)).not.toBe(key);}});
 it('preserves partial safe answers and diagnostics after persistence',()=>{const text=JSON.stringify({mode:'extractive-rag',answer:'Raw',citations:[],verification:{status:'partial',verified:true,safe_answer:'Founded: 2012. Missing countries.',reason:'missing_facts',repair_attempts:[{attempt:1}]}});expect(parseRag(text)?.verification?.safe_answer).toContain('Missing countries');expect(parseRag(text)?.verification?.status).toBe('partial');});
});
