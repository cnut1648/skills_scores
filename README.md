-   Based on Onet skills (or Competencies) & jobs (or Occupations) from latest (25.1) database, parse as a biparite graph where $V = \{ occupations \} \oplus \{ skills \}$

-   Pull job postings from USAJobs, which is more thorough and more structured than Linkedin (but we still keep the scraper in `scraper` dir and provide transformer to schema.org scheme) and [Virginia Dataset](https://opendata-cs-vt.github.io/ccars-jobpostings/), thus enable better skill extraction; it is also up to date so we decide not to use Kaggle 19,000 [job postings](https://www.kaggle.com/madhab/jobposts) that were posted through the Armenian human resource portal CareerCenter.

-   Transform jobposting to [schema.org JobPosting schema](https://schema.org/JobPosting) to enable skill extraction

-   apply data cleansing in `utils.py`

-   three most efficient skill extractors:

    1.  Grammer based NP Chunking

        Note this one doesn't align extracted skills to Onet skills

    -   Exact match

        using [Trie](https://www.wikiwand.com/en/Trie) to optimize regular expression

    -   Fuzzy search

        Fork of [symspell](https://github.com/wolfgarbe/SymSpell) **1 million times faster** through Symmetric Delete spelling correction algorithm

-   generate new scores from the extracted skills and ontology skill:

    Assume for job $j$ we have $S$ which are the skills required by $j$ from ontology (Onet in this case)

    From the extracted skills we only have the counts of skills. Similar to the traditional approach in NLP pertaining to co-occurance matrix we use MLE to estimate $P(\text{skill }s \in S \mid \text{job } j)$ i.e. let $q(s \mid j) = \dfrac{count(s, corpus_{j})}{\sum_{s \in S}count(s, corpus_j))}$, where $count(s, corpus_j)$ is the number of occurrences of skill $s$ in the $corpus_j$, which in this case are the USAJobs job postings for job $j$.

    However the distribution of counts of the extracted skills are highly biased and skewed, where most of them are 0 (they never show up in the corpus, but do notice that many of the Onet skills are not likely to show up in the job postings for example writing); while if some skills have positive counts, it is always a large number like greater or equal to 10.

    Thus to cope with count being 0 and assign estimate with positive probability we apply smoothing:

    1.  add-$\alpha$  [Chen and Goodman, 1999, Goodman,
        2001, Lidstone, 1920]

        `smoothed` column in the result csv

    2.  maximum division

         $q(s \mid j)_{max\_divide} = \dfrac{count(s, corpus_{j})}{\max _{s \in S} count(s, corpus_j))}$

        `max_divide` column in the result csv

    3.  smoothed maximum division

        add-$\alpha$ on $q(s\mid j)_{max\_divide}$

        `max_divide_smoothed` column in the result csv

    4.  smoothed minimum division

        `min_divide_smoothed ` column in the result csv

    5.  log smoothed

        apply $log_{10}(\cdot)$ on add-$\alpha$.

        `log_smoothed`column in the result csv

    Others we tried but not working well:

    1.  back-off or Jelinek mercer interpolated backoff [Chen and Goodman, 1999, Jelinek and Mercer, 1980]: works for n-gram not in here

    2.  Laplace smoothing: works well in trigram but not here

    3.  PMI [Dagan et al., 1994, Turney, 2001, Turney and Pantel, 2010]: define for bi-gram not suitable for this task. 

    4.  downweight skills s for job j

        $w_{sj} = count(s, corpus_j) \cdot \ln (\dfrac{|S|}{|corpus_j|})$

        not so effective

    Once we have the $q(s \mid j)$ for each $s \in S$, we can update scores for s $u(corpus_j;ontology)$ as a convex combination of $u_0$ and $w_s \cdot u_0$, i.e. the weight learned by job postings

    $$u_{new} = \lambda \cdot u_0 + (1-\lambda) \cdot w_s\cdot u_0$$

    in here we pick $\lambda = 0.9$. So we assign more weights on Onet scores and use job postings to represent contemporary shift on required jobs

    Onet only have scores for these 5 categories, plus Onet's hot/not hot tech skills

    We use $q(s \mid j)$ to estimate $w_s$, where we need to map probability 0-1 to scale 1-5





NER

We create NER model as:

1.  Embedding: FastText [Mikolov et al., 2018] trained on web context scrapped by crawlers + forward & backword Contextual String trained on 1 billion words news [Akbik, Blythe, and Vollgraf, 2018]

    We believe combined these embeddings each word would represent accurately based on academic and non-academic context

2.  2 BiLSTM layers

3.  CRF

4.  dropout, epoch annealing and learning rate schedulers…

Although NER is able to extract useful and more concrete skills (eg. onet doesn't have `Russian` as a skill but `foreign language` but NER is able to extract Russian as a skill ) but if we use skills extracted from NER then we need an another ontology to update the scores

# set up

First git clone this repository, it is suggested that you create a virtual env to use this function so that it won't conflict with your other packages.

Run `pip install -r requirements.txt` and then you (should be) are done with downloading packages.

Then take a look at `config.py` to configure the project settings.

# skills scores

to run application

```bash
python updateScores.py 11-3012.00 "Administrative Services Managers" "Business Manager" --alpha 0.7
```

where onet id is `11-3012.00` and the corresponding related jobs are `Administrative Services Managers` and `Business Manager`

to see all available commands please see `python updateScores.py --help`

Note the first time to run this command onet data would be downloaded to your local machine. By default the download directory is `./dataset`.

This script would generate two files whenever it finish the updating process. 1. it generates the pickle files that contains the job postings; 2. it generates the csv files that contains the scores, updated scores, probabilities etc..
