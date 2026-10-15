export type Workflow={id:string;name:string;agent_ids:string[];retry_from:number;max_revisions:number;max_calls:number;max_total_tokens:number;timeout_seconds:number;status:string;created_at:string};
export type WorkflowForm=Omit<Workflow,'id'|'created_at'>;
export type WorkflowNode={agent_id:string;name:string;role:string};
export type Artifact={stage_index:number;agent_id:string;role:string;attempt:number;output:StageOutput};
export type StageOutput={summary:string;data:Record<string,unknown>;decision?:'approve'|'revise';feedback?:string};
export type WorkflowRun={id:string;workflow_id:string;title:string;prompt:string;status:string;current_stage:number|null;current_agent_id:string|null;revisions:number;calls:number;input_tokens:number;output_tokens:number;duration_ms:number|null;error:string|null;created_at:string;result:{artifacts:Artifact[];review:StageOutput}|null;graph:WorkflowNode[];retry_from:number;limits:{max_revisions:number;max_calls:number;max_total_tokens:number;timeout_seconds:number}};
export type WorkflowStep={id:string;run_id:string;stage_index:number;attempt:number;agent_id:string;agent_name:string;role:string;status:string;input:Record<string,unknown>;output:StageOutput|null;raw_output:string|null;error:string|null;input_tokens:number;output_tokens:number;duration_ms:number|null;created_at:string};
