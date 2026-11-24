// node tests/pvm_parity.js data.json  -> prints docs/pvm.js decomposition as JSON (used by test_pvm.py)
const {decomposePVM}=require("../docs/pvm.js");
const lines=JSON.parse(require("fs").readFileSync(process.argv[2],"utf8"));
console.log(JSON.stringify({total:decomposePVM(lines,false),monthly:decomposePVM(lines,true)}));
