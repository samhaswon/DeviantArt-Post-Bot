from datetime import datetime, timedelta
import json
import os
import re
import sched
import time
from typing import List

from da_token_manager import DATokenManager
from da_poster import Poster


# Global stuff
TOKEN: str = ""
DEBUG: bool = True
DEBUG_NO_POST: bool = True

# Load config
with open("da_config.json", "r") as json_file:
    da_config_dict: dict = json.load(json_file)
    for key in da_config_dict.keys():
        if isinstance(da_config_dict[key], int):
            da_config_dict[key] = str(da_config_dict[key])
    DEBUG = eval(da_config_dict.get("debug", "True"))
    DEBUG_NO_POST = eval(da_config_dict.get("debug_no_post", "True"))

# Set up the token manager and poster
token_manager = DATokenManager(da_config_dict, debug=True)
TOKEN = token_manager.token     # keep this up to date during testing
poster = Poster()

# Initialize the scheduler
scheduler = sched.scheduler(time.time, time.sleep)


def update_token() -> None:
    """
    Makes sure the token is valid. Call this before performing an action on the API.
    :return: None
    """
    global TOKEN
    TOKEN = token_manager.token


def make_post(directory: str, num_images: int, galleries: List[str], tags: List[str]) -> None:
    if not os.path.isdir(directory):
        print(f"{directory} is not a directory!")
        return
    files = [
        x for x in os.scandir(directory)
        if os.path.isfile(x.path) and re.search(r"\.jpe?g$|\.png$", x.path)
    ]
    if len(files) == 0:
        print(f"Out of files to post in {directory}")
        return

    files.sort(key=lambda x: int(re.sub(r"\D", '', x.name)))

    # Extract only the number of files we're posting
    files = files[:num_images]

    if DEBUG:
        print(f"Posting files: {files}")

    update_token()
    for file in files:
        base_name = file.name[:file.name.rfind(".")]
        base_path = file.path[:file.path.rfind(".")]
        if os.path.isfile(base_path + ".txt"):
            with open(base_path + ".txt", "r") as comment_file:
                comment = comment_file.read()
        else:
            comment = ""
        post_name = re.sub(r"_+|\s\s+", " ", base_name)
        if DEBUG:
            print(f"Posting {post_name} from {file.path}\n"
                  f"with {comment=}; {tags=}; {galleries=}")

        # Post the image
        if not DEBUG_NO_POST:
            poster.upload_and_submit(file.path,
                                     TOKEN,
                                     post_name,
                                     comment,
                                     tags,
                                     galleries,
                                     debug=DEBUG)
            os.remove(file.path)


def post_scheduler() -> None:
    global da_config_dict, scheduler
    for post_type in da_config_dict["post_config"].keys():
        posting_type = da_config_dict["post_config"][post_type]["type"]
        if posting_type.lower() == "rotation":
            # Take advantage of the fact that the token manager has a shallow copy of the dictionary
            da_config_dict["post_config"][post_type]["last_posted"] += 1
            # token_manager.extra_config["post_config"][post_type]["last_posted"] += 1
            if (da_config_dict["post_config"][post_type]["last_posted"] >=
                    len(da_config_dict["post_config"][post_type]["directories"])):
                da_config_dict["post_config"][post_type]["last_posted"] = 0
                # token_manager.extra_config["post_config"][post_type]["last_posted"] = 0
            token_manager.increment_rotation_config(post_type, da_config_dict["post_config"][post_type]["last_posted"])

            # Figure out what we're posting
            post_index = da_config_dict["post_config"][post_type]["last_posted"]
            directory = da_config_dict["post_config"][post_type]["directories"][post_index]
            tags = da_config_dict["post_config"][post_type]["tags"][post_index]

        elif posting_type.lower() == "daily":
            # Figure out what we're posting
            directory = da_config_dict["post_config"][post_type]["directory"]
            tags = da_config_dict["post_config"][post_type]["tags"]

        else:
            print(f"Invalid configuration for posting type: {posting_type}")
            exit(1)

        # Grab common config arguments
        images_per_day: int = da_config_dict["post_config"][post_type]["images_per_day"]
        time_of_day: str = da_config_dict["post_config"][post_type]["time"]
        galleries: List[str] = da_config_dict["post_config"][post_type]["galleries"]

        # Figure out when to schedule the posting
        hour, minute = tuple(time_of_day.split(":"))
        hour, minute = int(hour), int(minute)
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If the target time is already past today, schedule for tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)
        delay = (target_time - now).total_seconds()
        scheduler.enter(delay, 1, make_post, argument=(directory, images_per_day, galleries, tags))
        print(f"Scheduled posting of {post_type} for {target_time}")


# Main loop to run the scheduler
def run_scheduler():
    while True:
        # Schedule the task
        post_scheduler()

        # Run the scheduler
        scheduler.run()

        # Wait for one hour before checking again
        time.sleep(3600)


if __name__ == '__main__':
    # Print config information
    print(f"{DEBUG=}\n{DEBUG_NO_POST=}")
    print("Config\n", "-" * 20, "\n")
    for post_type in da_config_dict["post_config"].keys():
        print(json.dumps(da_config_dict["post_config"][post_type], indent=4))
    print("\n", "-" * 20, "\n")

    # Get everything going
    run_scheduler()
