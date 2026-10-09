// Used only by an isolated CLI import project, never by a bot handler or endpoint.
export async function executeImportBatch(db,plan,input={}) {
  const start=input.start??0,limit=input.limit??100;
  if(!Number.isSafeInteger(start)||start<0||start>plan.statements.length||
      !Number.isSafeInteger(limit)||limit<1||limit>100)throw new RangeError('Invalid import batch range');
  const end=Math.min(plan.statements.length,start+limit);
  let inserted=0;
  for(let index=start;index<end;index++) {
    const statement=plan.statements[index];
    const result=await db.run(statement.query,statement.params);
    inserted+=result.rowsAffected;
  }
  // Each insert is independently replay-safe. An interrupted batch is rerun from its same start.
  return {start,nextStart:end,total:plan.statements.length,inserted,skipped:end-start-inserted,
    complete:end===plan.statements.length};
}
