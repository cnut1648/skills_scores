from pathlib import Path
from time import time

from functools import partial

from argparse import ArgumentParser
import pickle
import concurrent.futures

from torcherist.dataset.ontology.onet import Onet
from torcherist.algorithms.skill_extractors import (
    FuzzyMatchSkillExtractor,
    ExactMatchSkillExtractor,
)

from typing import List

from config import USAJOBS_TOKEN, USAJOBS_EMAIL, PICKLE_DB_DIR_NAME, ONET_DIR
from scraper.fetchUSAJobs import USAJobsFetcher
from utils import (
    tech_skills_or_having_scores, skills_from_USAJobs,
    calculate_new_score
)

from datetime import date


def getOnet(onet_corresponding_job_id):
    onet = Onet(onet_dir=Path(ONET_DIR))
    onet = onet.filter_by(lambda e: e.occupation.identifier == onet_corresponding_job_id)
    onet = onet.filter_by(tech_skills_or_having_scores)
    onet.name = onet_corresponding_job_id
    onet.competency_framework.name = onet_corresponding_job_id
    onet.competency_framework.description = onet_corresponding_job_id
    onet.print_summary_stats()
    return onet


def getFetcher(jobs):
    with USAJobsFetcher(USAJOBS_TOKEN, USAJOBS_EMAIL) as fetcher:
        try:
            jobpostings: dict = fetcher.all_postings_of(jobs)
        except Exception as e:
            print("Your token or email is wrong. Please double check again.")
            raise e
        jobs_str = [
            "_".join(job.split(" "))
            for job in jobs
        ]
        try:
            save_dir = Path(__file__).parent / PICKLE_DB_DIR_NAME
            save_dir.mkdir(parents=True, exist_ok=True)
            with open(save_dir / f"USAJobs-{'&'.join(jobs_str)}.pkl", "wb") as f:
                pickle.dump(jobpostings, f)
        except Exception as e:
            print("error in saving pickle file: ", e)
            print("ignoring...")
        return jobpostings


def updateScores(jobs: List[str],
                 onet_corresponding_job_id: str,
                 skill_extractor: str = "exact_match",
                 alpha: float = 1.0,
                 based_prob: str = "smoothed"
                 ):
    assert skill_extractor in ["exact_match", "fuzzy_search"]
    assert based_prob in ["smoothed", "max_divide", "max_divide_smoothed", "min_divide_smoothed", "log_smoothed"]

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
            except Exception as e:
                print(e)
                # print(e.message)
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
    parser = ArgumentParser()
    parser.add_argument('onet_corresponding_job_id', type=str, help="onet SOC id for the job you provided")
    parser.add_argument("jobs", type=str, nargs="+",
                        help="list of jobs that you want to fetch job postings and update scores")
    parser.add_argument("--extractor", dest="skill_extractor",
                        type=str, nargs="?", default="exact_match",
                        help="type of skill extractor for extracting skills from jobpostings, either 'exact_match' or "
                             "'fuzzy_search'")
    parser.add_argument("--alpha", type=float,
                        nargs="?", help="alpha in add-alpha smoothing, default = 1.0",
                        default=1.0)
    parser.add_argument("--prob", dest="based_prob", nargs="?", default="smoothed",
                        help="use which prob to update the scores, must be 'smoothed' | 'max_divide' | "
                             "'max_divide_smoothed' | 'min_divide_smoothed' | 'log_smoothed' "
                        )
    args = parser.parse_args()

    start = time()
    df = updateScores(jobs=args.jobs,
                      onet_corresponding_job_id=args.onet_corresponding_job_id,
                      skill_extractor=args.skill_extractor,
                      alpha=args.alpha,
                      based_prob=args.based_prob
                      )

    if df is not None:
        df.to_csv(f"scores-{args.onet_corresponding_job_id}::{date.today()}.csv")
    print("Updating for scores took %.3f seconds" % (time() - start))
