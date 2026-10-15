import {it,expect} from 'vitest';
import {parseRag} from './knowledge';
import {ragEn,ragRu} from './rag-i18n';
it('parses RAG and preserves source page and mock marker',()=>{
 const row={mode:'extractive-rag',mock:true,provider:'mock',found:true,question:'q',answer:'quote',citations:[{document:'a.pdf',page:2,quote:'quote'}]};
 expect(parseRag(JSON.stringify(row))).toEqual(row);expect(parseRag('[MOCK] previous single agent')).toBeNull();expect(parseRag(null)).toBeNull();
});
it('all RAG states and errors have RU and EN messages',()=>{expect(Object.keys(ragRu).sort()).toEqual(Object.keys(ragEn).sort());for(const text of Object.values(ragRu))expect(text).toBeTruthy();});
