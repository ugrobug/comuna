import ast,json,statistics,subprocess,sys,time,tempfile,types
from pathlib import Path
sys.path.insert(0,str(Path('backend').resolve()))
from telegram_integration.health import JsonStatusFile,PollingStatus
from telegram_integration.runtime import TelegramPollingRuntime
old=subprocess.check_output(['git','show','7b38312:backend/telegram_integration/polling.py'],text=True)
new=Path('backend/telegram_integration/polling.py').read_text()
class Approvals:
 def __init__(self,*a):pass
 def drain(self,**kw):pass
updates=[{'update_id':i,'channel_post':{}} for i in range(100)]
def namespace(source):
 names={'TelegramUpdateProcessor','_polling_loop'}
 tree=ast.parse(source)
 tree.body=[x for x in tree.body if isinstance(x,(ast.ClassDef,ast.FunctionDef)) and x.name in names]
 ns={'Any':object,'print':lambda *a:None,'time':time,'TelegramApprovalPrompt':Approvals}
 for name in ['_send_bot_message_with_keyboard','_handle_callback_query','_handle_channel_post','_handle_inline_query','_handle_message','_handle_my_chat_member']:
  ns[name]=lambda *a:None
 exec(compile(tree,'benchmark','exec'),ns)
 return ns
oldns,newns=namespace(old),namespace(new)
measure={}
with tempfile.TemporaryDirectory() as directory:
 for variant in ['before','after']:
  elapsed=[]
  for _ in range(100):
   calls=[0]
   def fetch(method,*args):
    if method=='deleteWebhook':return {'ok':True}
    if calls[0]>=10:raise KeyboardInterrupt()
    batch=[dict(item,update_id=item['update_id']+100*calls[0]) for item in updates]
    calls[0]+=1
    return {'ok':True,'result':batch}
   if variant=='before':
    oldns['_fetch_telegram_json']=fetch
    run=lambda:oldns['_polling_loop']('test')
   else:
    status=PollingStatus(JsonStatusFile(directory+'/status.json'))
    runtime=TelegramPollingRuntime('test',fetch,newns['TelegramUpdateProcessor'](status.progress),Approvals(),status)
    def run():
     while True:runtime.step()
   start=time.perf_counter()
   try:run()
   except KeyboardInterrupt:pass
   elapsed.append((time.perf_counter()-start)*1000)
  measure[variant]={'median_ms_per_1000_mock_updates':round(statistics.median(elapsed),3),'samples':len(elapsed)}
 print(json.dumps(measure))
