import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
async function proxy(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const host = request.headers.get('host') ?? '';
  if (!/^(127\.0\.0\.1|localhost)(:\d+)?$/.test(host)) return NextResponse.json({error:{code:'forbidden_host'}},{status:403});
  const origin = request.headers.get('origin');
  if (origin && origin !== `${request.nextUrl.protocol}//${host}`) return NextResponse.json({error:{code:'forbidden_origin'}},{status:403});
  if (!['GET','HEAD'].includes(request.method) && !origin) return NextResponse.json({error:{code:'forbidden_origin'}},{status:403});
  const {path} = await context.params;
  if (!path.length || !['workspaces','auth','users','agents','tasks','executions','dashboard','providers','models','tools','workflows','workflow-runs','tool-calls','mcp-servers','knowledge','evaluation','llm','validation'].includes(path[0]) || path.some(p => !/^[a-zA-Z0-9_-]+$/.test(p))) return NextResponse.json({error:{code:'not_found'}},{status:404});
  try {
    const joined=path.join('/');
    const preparation=joined==='evaluation/install'||/^validation\/prepare\/(v1|v2)$/.test(joined)||/^workspaces\/[a-zA-Z0-9_-]+\/smoke(?:\/prepare)?$/.test(joined);
    const headers:Record<string,string>={'Content-Type':'application/json'};
    for(const name of ['cookie','authorization','x-csrf-token','origin']){const value=request.headers.get(name);if(value)headers[name]=value;}
    if(!headers.origin)headers.origin=`${request.nextUrl.protocol}//${host}`;
    const upload=(path.join('/')==='knowledge/documents'||(path[0]==='workspaces'&&path.slice(2).join('/')==='knowledge/documents'))&&request.method==='POST';
    let body: string|ArrayBuffer|undefined;
    if (upload) {
      const reader=request.body?.getReader();const pieces:Uint8Array[]=[];let size=0;
      if (reader) while (true) {
        const part=await reader.read();if(part.done)break;size+=part.value.byteLength;
        if(size>5*1024*1024){await reader.cancel();return NextResponse.json({error:{code:'pdf_too_large'}},{status:413});}
        pieces.push(part.value);
      }
      const bytes=new Uint8Array(size);let cursor=0;for(const piece of pieces){bytes.set(piece,cursor);cursor+=piece.byteLength;}body=bytes.buffer;
    } else body=['GET','HEAD'].includes(request.method)?undefined:await request.text();
    if (body && (typeof body==='string'?body.length:body.byteLength) > (upload?5*1024*1024:100000)) return NextResponse.json({error:{code:'payload_too_large'}},{status:413});
    const response = await fetch(`${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/${path.join('/')}${request.nextUrl.search}`, {
      method: request.method, headers: {...headers,'Content-Type':upload?'application/pdf':'application/json'}, body,
      cache: 'no-store', signal: AbortSignal.timeout(preparation?300000:65000)
    });
    const result=new NextResponse(response.status === 204 ? null : await response.text(), {status:response.status, headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
    for(const cookie of response.headers.getSetCookie())result.headers.append('Set-Cookie',cookie);
    return result;
  } catch {
    return NextResponse.json({error:{code:'backend_unavailable'}},{status:503});
  }
}
export {proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE, proxy as PATCH};
