from time import time

from functools import partial

import pickle
import concurrent.futures

from torcherist.dataset.ontology.onet import Onet
from torcherist.algorithms.skill_extractors import (
    FuzzyMatchSkillExtractor,
    ExactMatchSkillExtractor,
)

from typing import List

from config import USAJOBS_TOKEN, USAJOBS_EMAIL
from scraper.fetchUSAJobs import USAJobsFetcher
from utils import (
    tech_skills_or_having_scores, skills_from_USAJobs,
    calculate_new_score
)

from datetime import date


def getOnet(onet_corresponding_job_id):
    onet = Onet()
    onet = onet.filter_by(lambda e: e.occupation.identifier == onet_corresponding_job_id)
    onet = onet.filter_by(tech_skills_or_having_scores)
    onet.name = onet_corresponding_job_id
    onet.competency_framework.name = onet_corresponding_job_id
    onet.competency_framework.description = onet_corresponding_job_id
    onet.print_summary_stats()
    return onet


def getFetcher(jobs):
    fetcher = USAJobsFetcher(USAJOBS_TOKEN, USAJOBS_EMAIL)
    try:
        jobpostings: dict = fetcher.all_postings_of(jobs)
    except Exception as e:
        print("Your token or email is wrong. Please double check again.")
        raise e
    jobs_str = [
        "_".join(job.split(" "))
        for job in jobs
    ]
    with open(f"db/USAJobs-{'&'.join(jobs_str)}.pkl", "wb") as f:
        pickle.dump(jobpostings, f)
    return jobpostings


def updateScores(jobs: List[str],
                 onet_corresponding_job_id: str,
                 skill_extractor: str = "exact_match",
                 alpha: float = 1.0,
                 based_prob: str = "smoothed"
                 ):
    assert skill_extractor in ["exact_match", "fuzzy_search"]
    assert based_prob in ["smoothed", "max_divide", "max_divide_smoothed", "min_divide_smoothed"]

    with concurrent.futures.ThreadPoolExecutor(10) as executor:
        future2data = {
            executor.submit(getOnet, onet_corresponding_job_id): "onet",
            executor.submit(getFetcher, jobs): "jobpostings"
        }

        for future in concurrent.futures.as_completed(future2data):
            data = future2data[future]
            try:
                if data == "onet":
                    onet = future.result()
                else:
                    jobpostings = future.result()
            except Exception:
                return

    if skill_extractor == "exact_match":
        skill_extractor = ExactMatchSkillExtractor(onet.competency_framework)
    else:
        skill_extractor = FuzzyMatchSkillExtractor(onet.competency_framework)

    df = skills_from_USAJobs(ontology=onet,
                             usaJobs=jobpostings,
                             skill_extractor=skill_extractor,
                             alpha=alpha)
    calculate_row_score: callable = partial(calculate_new_score, df=df, prob=based_prob)
    df["new score"] = df.apply(calculate_row_score, axis=1)
    return df


if __name__ == '__main__':
    start = time()
    df = updateScores(jobs=['Administrative Services Managers', 'Business Manager'],
                      onet_corresponding_job_id='11-3012.00',
                      skill_extractor="exact_match"
                      )
    df.to_csv(f"{date.today()}-update_scores.csv")
    print("Updating for scores took %.3f seconds" % (time() - start))
