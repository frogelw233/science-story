"""Run real local unittest suite and save machine-readable results."""
import io
import json
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))


class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.records=[]
    def addSuccess(self,test):
        super().addSuccess(test)
        self.records.append({"test":test.id(),"status":"pass"})
    def addFailure(self,test,err):
        super().addFailure(test,err)
        self.records.append({"test":test.id(),"status":"fail","detail":self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err)
        self.records.append({"test":test.id(),"status":"error","detail":self._exc_info_to_string(err,test)})
    def addSkip(self,test,reason):
        super().addSkip(test,reason)
        self.records.append({"test":test.id(),"status":"skip","detail":reason})


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    buffer=io.StringIO()
    result=unittest.TextTestRunner(stream=buffer,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.discover(str(ROOT/"tests")))
    out=ROOT/"reports"
    out.mkdir(exist_ok=True)
    (out/"unit-tests.txt").write_text(buffer.getvalue(),encoding="utf-8")
    (out/"unit-tests.json").write_text(json.dumps({"executed_at":datetime.now(timezone.utc).isoformat(),"python":platform.python_version(),"platform":platform.system(),"scope":"offline unit tests; network mocks are not end-to-end evidence","run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),"tests":result.records},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(buffer.getvalue())
    raise SystemExit(not result.wasSuccessful())
