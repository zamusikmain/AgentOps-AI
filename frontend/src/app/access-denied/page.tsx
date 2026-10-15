import {AuthGate} from '@/components/authentication';
import Workspace from '@/components/application-workspace';
export default function Page(){return <AuthGate initialView='denied' initialReason=''><Workspace/></AuthGate>;}
