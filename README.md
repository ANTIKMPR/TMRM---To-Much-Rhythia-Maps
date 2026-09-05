## ⬜ TMRM - To Much Rhythia Maps ⬜

Program, that downloads every map in category u type

The program is started like project only for self using, but i wanted to public it for others, other things from --help

## Templates

"--min 3  --max 6 --status RANKED" , "--min 6 --max 9 --status UNRANKED"

## ❔ Q&A:

**Q: How to use it?**

A: Type "python rhythia_downloader.py --min (minimum star rate) --max (maximum star rate) --status (RANKED or UNRANKED)"

**Q: Why its not working?!**

A: Try download "Requests" with pip "pip install requests" or turn off proxy and other programs that can change wifi, like VPN's and other

**Q: Is this vibecode?**

A: Yup, its fully vibecoded, i just controlled the progress

**Q: Are this program gonna be like py file only? (no exe, cry about it)**

A: Yeah, im to lazzy to make exe file, and i dont like it

## Options:
```text
  -h, --help            show this help message and exit
  --min MIN             Minimum star rating (e.g. 3)
  --max MAX             Maximum star rating (e.g. 5)
  --status {RANKED,UNRANKED,QUALIFIED,ALL}
                        Map status: RANKED (awards RP), UNRANKED, QUALIFIED, or ALL (loop through every status). Default: ALL.
  --out OUT             Folder to save maps into (default: ./rhythia_maps)
  --workers WORKERS     Number of parallel downloads (default: 6)
  --delay DELAY         Delay between API page requests, in seconds (default: 0.2)
  --no-proxy            Ignore the system proxy entirely (useful if you hit ConnectionResetError/10054)
  --proxy PROXY         Explicitly set a proxy, e.g. [http://127.0.0.1:7890/](http://127.0.0.1:7890/)
  --session SESSION     Session token from DevTools (Payload of the getBeatmaps request), if anonymous requests get blocked (400/401)
  --clear               Delete all map files from the --out folder (default ./rhythia_maps) and exit, without downloading anything.
  --debug-fields        Print every field of the first found map (JSON) before filtering — for debugging.
