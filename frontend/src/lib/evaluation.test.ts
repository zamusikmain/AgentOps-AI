import {describe,it,expect} from 'vitest';
import {evaluationEn,evaluationRu} from './evaluation-i18n';
import {parseRag} from './knowledge';
describe('Answer reliability presentation',()=>{
 it('preserves old answers and new safe verification fields',()=>{const old={mode:'extractive-rag',answer:'Legacy quote',citations:[]};expect(parseRag(JSON.stringify(old))?.answer).toBe('Legacy quote');const newer={...old,verification:{status:'insufficient_evidence',safe_answer:'Insufficient information',verified:false,reason:'no_evidence'}};expect(parseRag(JSON.stringify(newer))?.verification?.verified).toBe(false);});
 it('has matching localized statuses and machine reasons',()=>{expect(Object.keys(evaluationRu).sort()).toEqual(Object.keys(evaluationEn).sort());for(const s of ['supported','unsupported','insufficient_evidence','conflicting_evidence','not_applicable'])expect(evaluationEn[s as keyof typeof evaluationEn]).toBeTruthy();});
});
