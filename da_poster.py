import re
import socket
import time
from typing import List

import requests


class Poster:
    STASH_UPLOAD_URL = "https://www.deviantart.com/api/v1/oauth2/stash/submit"
    STASH_PUBLISH_URL = "https://www.deviantart.com/api/v1/oauth2/stash/publish"

    @staticmethod
    def _is_dns_error(exception: Exception) -> bool:
        """
        Detect DNS / name-resolution errors wrapped by requests exceptions.
        """
        dns_error_markers = (
            "nameresolutionerror",
            "temporary failure in name resolution",
            "name or service not known",
            "nodename nor servname provided",
            "getaddrinfo failed",
        )
        seen = set()
        stack = [exception]
        while stack:
            current = stack.pop()
            if current is None:
                continue
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)

            if isinstance(current, socket.gaierror):
                return True
            if any(marker in str(current).lower() for marker in dns_error_markers):
                return True

            if getattr(current, "__cause__", None):
                stack.append(current.__cause__)
            if getattr(current, "__context__", None):
                stack.append(current.__context__)
            for arg in getattr(current, "args", ()):
                if isinstance(arg, BaseException):
                    stack.append(arg)
        return False

    def upload_and_submit(self,
                          file_path: str,
                          token: str,
                          title: str,
                          artist_comments: str,
                          tags: List[str],
                          folders: List[str],
                          is_mature: bool = True,
                          debug: bool = False,
                          back_off_time: int = 2,
                          is_ai_generated: bool = False,
                          ) -> None:
        """
        Upload and submit an image to Deviantart.
        :param file_path: Path to the file to upload.
        :param token: The `access_token` to be used for the upload.
        :param title: The title of the deviation.
        :param artist_comments: The comment body of the deviation.
        :param tags: The tags of the deviation.
        :param folders: The folders to post the deviation in to.
        :param is_mature: If the deviation should be tagged as mature.
        :param debug: Print debugging information.
        :param back_off_time: Time to wait for the rate limit to expire.
        :param is_ai_generated: If the deviation should be tagged as AI.
        :return: None
        """
        if back_off_time >= 1024:
            raise RuntimeError(
                f"Backoff time limit exceeded ({back_off_time} seconds), so ending here."
                f"Please check previous logs for more details for the reason."
            )
        # Truncate title
        title = title[:50]
        # Upload image
        params = {
            "access_token": token,
            "title": title,
            "artist_comments": artist_comments,
            "is_mature": is_mature,
        }
        if len(params["artist_comments"]) <= 1:
            del params["artist_comments"]

        encoded_tags = {f"tags[{i}]": tag for i, tag in enumerate(tags)}
        data = {**params, **encoded_tags}
        with open(file_path, "rb") as image_file_pointer:
            image_file = image_file_pointer.read()
            if re.search(r"\.jpe?g$", file_path):
                files = {
                    'image': ('image.jpg', image_file, 'image/jpeg')
                }
            elif re.search(r"\.png$", file_path):
                files = {
                    'image': ('image.png', image_file, 'image/png')
                }
            else:
                raise RuntimeError(f"Invalid file type for file at {file_path}")

        upload_failed = False
        dns_upload_failed = False
        json_parsing_failed = False
        result = None
        upload_status = 0
        try:
            result = requests.post(self.STASH_UPLOAD_URL, data=data, files=files)
            upload_status = result.status_code
            if debug:
                print(f"Raw {result.text=}")
            result = result.json()
        except (requests.exceptions.JSONDecodeError, requests.exceptions.InvalidJSONError):
            json_parsing_failed = True
        except requests.exceptions.ConnectionError as exc:
            upload_failed = True
            dns_upload_failed = self._is_dns_error(exc)

        if json_parsing_failed or upload_failed or result.get("status", "failure") != "success":
            if json_parsing_failed:
                print(f"JSON parse error encountered. Backing off for {back_off_time} seconds.")
                time.sleep(back_off_time)
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time ** 2
                )
                return
            elif upload_failed:
                if dns_upload_failed:
                    print(f"DNS resolution error encountered during upload. Waiting for 1 second.")
                    time.sleep(1)
                else:
                    print(f"Upload error encountered. Backing off for {back_off_time} seconds.")
                    time.sleep(back_off_time)
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time
                )
                return
            elif upload_status == 429:
                print(f"Rate limit encountered. Backing off for {back_off_time} seconds.")
                time.sleep(back_off_time)
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time ** 2
                )
                return
            elif upload_status >= 500:
                print(f"Deviantart had a server error {upload_status}. Waiting and trying again", end="")
                for i in range(3):
                    time.sleep(20)
                    print(".", end="")
                print()
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time ** 2
                )
                return
            elif result.get("status", "failure") == "error" and result.get("error", "server_error"):
                error_description = result.get("error_description", "none")
                if error_description != "none":
                    print(
                        f"Deviantart had a server error ({error_description}). Waiting and trying again. "
                        f"Hint: try uploading this image in the web UI, as this is a vague error from DA."
                    )
                else:
                    print(
                        f"Deviantart had a server error {upload_status}. Waiting and trying again. "
                        f"Hint: try uploading this image in the web UI, as this is a vague error from DA."
                    )
                time.sleep(back_off_time)
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time + 2  # Don't do exponential backoff, just wait a little longer.
                )
                return
            else:
                raise RuntimeError(f"Unable to upload image!\n"
                                   f"{result=}")
        if debug:
            print(f"JSON parsed {result=}")

        # Post image
        params = {
            "access_token": token,
            "allow_free_download": True,
            "add_watermark": False,
            # "catpath": "visual_art",
            "feature": "true",
            "galleryids": folders,
            "request_critique": False,
            "allow_comments": True,
            "display_resolution": 0,
            "sharing": "allow",
            "is_ai_generated": is_ai_generated,
            "noai": not is_ai_generated,  # If AI, don't allow in datasets
            "license_options": {
                "creative_commons": False,
                "commercial": False,
                "modify": "no"
            },
            "itemid": result["itemid"]
        }
        if is_mature:
            # Some safe defaults for mature content
            params["is_mature"] = True
            params["mature_level"] = "strict"
            params["mature_classification"] = ["nudity", "sexual"]
        publish_failed = False
        dns_publish_failed = False
        try:
            post_result = requests.post(self.STASH_PUBLISH_URL, params=params)
        except requests.exceptions.ConnectionError as exc:
            publish_failed = True
            dns_publish_failed = self._is_dns_error(exc)
        if publish_failed or post_result.status_code > 399:
            if publish_failed:
                if dns_publish_failed:
                    print(
                        f"DNS resolution error during publish request. Reattempting upload. "
                        f"You may also want to check your stash."
                    )
                    time.sleep(1)
                else:
                    print(
                        f"Publish request failed. Reattempting upload after {back_off_time} seconds. "
                        f"You may also want to check your stash."
                    )
                    time.sleep(back_off_time)
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time
                )
                return
            elif post_result.status_code == 400:
                print(
                    f"Deviantart broke most likely. Reattempting upload after {back_off_time} seconds. "
                    f"You may also want to check your stash."
                )
                print(f"Response:\n{post_result.text=}")
                time.sleep(back_off_time)
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time ** 2
                )
                return
            elif upload_status == 429:
                retry_count = 1
                while post_result.status_code > 399 and retry_count < 20:
                    print(f"Rate limit encountered. Backing off for {back_off_time} seconds.")
                    time.sleep(back_off_time)
                    post_result = requests.post(self.STASH_PUBLISH_URL, params=params)
                    back_off_time = back_off_time ** 2
                    if post_result.status_code > 399:
                        print(f"Retry count: {retry_count}")
                    retry_count += 1
                if post_result.status_code > 399:
                    print(f"Unable to post deviation {title}")
                    return
            elif post_result.status_code in {500, 503}:
                print(f"Deviantart had a server error {post_result.status_code}. Waiting and trying again")
                retry_count = 1
                while post_result.status_code > 399 and retry_count < 20:
                    print(f"Backing off for {back_off_time} seconds")
                    time.sleep(back_off_time)
                    post_result = requests.post(self.STASH_PUBLISH_URL, params=params)
                    back_off_time = back_off_time ** 2
                    if post_result.status_code > 399:
                        print(f"Retry count: {retry_count}")
                    retry_count += 1
                if post_result.status_code > 399:
                    print(f"Unable to post deviation {title}")
                    return
            else:
                raise RuntimeError(f"Failed to post image with error {post_result.status_code} {post_result.reason}\n"
                                   f"{post_result.text}")
        if debug:
            print(f"{post_result.text=}")
        try:
            post_result = post_result.json()
        except (requests.exceptions.JSONDecodeError, requests.exceptions.InvalidJSONError):
            print("Failed to post stashed deviation. "
                  "Trying the whole thing again. "
                  "You may also want to check your stash.")
            self.upload_and_submit(
                file_path,
                token,
                title,
                artist_comments,
                tags,
                folders,
                is_mature,
                debug,
                back_off_time ** 2
            )
            return
        else:
            print(f"Successfully posted deviation {post_result['deviationid']} at {post_result['url']}")
