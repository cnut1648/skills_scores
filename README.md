# set up

First git clone this repository, it is suggested that you create a virtual env to use this function 
so that it won't conflict with your other packages.

Run `pip install -r requirements.txt` and then you (should be) are done with downloading packages.

Then take a look at `config.py` to configure the project settings.

# skills_scores

to run application

```bash
python updateScores.py 11-3012.00 "Administrative Services Managers" "Business Manager" --alpha 0.7
```

Note the first time to run this command onet data would be downloaded to your local machine. By default the download
directory is `./dataset`.
