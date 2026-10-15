import {AuthGate} from '@/components/authentication';
import {AIWorkspace} from '@/components/ai-workspace';
export default function Page(){return <AuthGate initialView="ai"><AIWorkspace/></AuthGate>;}
