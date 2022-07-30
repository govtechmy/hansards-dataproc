import pandas as pd

with open("senarai_parlimen_dunBM.csv", 'r') as f:
    lines = f.readlines()

segments = []
for line in lines:
    # remove summary rows
    if "    " in line:
        continue
    segments += line.split(',')

# remove empty segments
segments = [segment.strip() for segment in segments if segment.strip()]

seg_id = 0
rows = []
state_cnt = 0
while seg_id < len(segments):
    if segments[seg_id] == "P.":
        pcode = segments[seg_id+1]
        pname = segments[seg_id+2]
        seg_id += 2
        if "W.P." in state:
            rows.append([state, int(pcode), pname, 0, None])
    elif segments[seg_id] == "N.":
        ncode = segments[seg_id + 1]
        nname = segments[seg_id + 2]
        rows.append([state,int(pcode),pname,int(ncode),nname])
        seg_id += 2
    else:
        state = segments[seg_id]
        state_cnt += 1
        print(state)
    seg_id += 1

# to find out missing P codes
numbers = set()
for i in range(222):
    numbers.add(i+1)

for row in rows:
    if row[1] in numbers:
        numbers.remove(row[1])

print(numbers)


df = pd.DataFrame(rows,columns=["state","pcode","pname","ncode","nname"])
# remove sarawak and sabah
df = df[df.state != "SABAH"]
df = df[df.state != "SARAWAK"]
df_sabah = pd.read_csv("SABAH.csv",names=["state","pcode","pname","ncode","nname"])
df_sarawak = pd.read_csv("SARAWAK.csv",names=["state","pcode","pname","ncode","nname"])
df = pd.concat([df, df_sabah])
df = pd.concat([df, df_sarawak])
print(df.info)
print(df.describe)
print("Number of states:",state_cnt)
print("Number of state electoral districts:",len(df.index))
df.to_csv('pncodes.csv', index=False)

df = df.drop(['ncode','nname'], axis=1)
df = df.drop_duplicates()
print("Number of federal electoral districts:",len(df.index))
df.to_csv('pcodes.csv', index=False)
