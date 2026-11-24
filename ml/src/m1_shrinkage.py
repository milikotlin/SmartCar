"""How much of the make / model / engine effect learned in the UK should shape an estimate for ANOTHER country?  Judged on two foreign markets never used to fit it
(India: Datasets 8 + 3; US: Dataset 6), after one global level factor. estimate = age_fuel(x) * (full(x) / age_fuel(x)) ** lam"""
import json
from m1_lab import *
kf,kv,kt=kaggle(); o=odometers(); of=o[o.part=="fit"]
so,_=synth_official(of,250000,seed=7); so["automatic"]=0.0
IND=pd.concat([kf,kv])[lambda d:d.source.isin(["d8_in","d3_cardekho"])].copy()
us=md.load_clean("d6_craigslist")[0]; us=us[us.fuel.isin(["petrol","diesel","hybrid","electric"])&us.age.between(1,25)].sample(60000,random_state=0)
us["make_model"]=[make_model_key(a,b) for a,b in zip(us.make,us.model)]; us["owner_type"]="Unknown"; us["engine_cc"]=np.where(us.fuel=="electric",0.0,np.nan)
M={"India":IND,"US":us}
def fit(cols):
    X=so.copy()
    p=ColumnTransformer([t for t in prep("frequency").transformers if t[0]!="make_model" or "mm" in cols])
    if "cc" not in cols: X["engine_cc"]=1500.0
    m=Pipeline([("prep",p),("model",xgb(n_estimators=600,min_child_weight=60,reg_lambda=10))]).fit(X,X.km)
    def pred(d):
        d=d.assign(automatic=0.0)
        if "cc" not in cols: d["engine_cc"]=1500.0
        return np.clip(m.predict(d),500,None)
    return pred
base,full=fit([]),fit(["cc","mm"])
out={}
for n,d in M.items():
    b,f=base(d),full(d); out[n]={}
    for lam in (0,.1,.2,.3,.5,.75,1):
        p=b*(f/b)**lam; p*=d.km.mean()/p.mean(); out[n][lam]=metrics(d.km,p)
    print(n,len(d),{l:(round(v["rmse"]),round(v["mae"]),round(v["r2"],3)) for l,v in out[n].items()},flush=True)
json.dump(out,open("ml/model1_transfer_shrinkage.json","w"),indent=1)
