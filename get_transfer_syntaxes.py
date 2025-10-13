from pydicom.uid import UID_dictionary

for uid, info in UID_dictionary.items():
    if "Transfer Syntax" in info[1]: #print out the transfer syntaxes
        print(f"{uid} - {info[0]}")
    else: # Print anything else and write to file
        with open('out', 'a') as f:
            f.write(uid + ' ... ' + str(info))
        print(uid, '...', info)
