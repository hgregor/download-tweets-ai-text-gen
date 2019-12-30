import twint
import fire
import re
import csv
from tqdm import tqdm
import logging
from datetime import datetime
from time import sleep

# Surpress random twint warnings
logger = logging.getLogger()
logger.disabled = True


def is_reply(tweet):
    """
    Determines if the tweet is a reply to another tweet.
    Requires somewhat hacky heuristics since not included w/ twint
    """

    # If not a reply to another user, there will only be 1 entry in reply_to
    if len(tweet.reply_to) == 1:
        return False

    # Check to see if any of the other users "replied" are in the tweet text
    users = tweet.reply_to[1:]
    conversations = [user['username'] in tweet.tweet for user in users]

    # If any if the usernames are not present in text, then it must be a reply
    if sum(conversations) < len(users):
        return True
    return False


def update_resume_file(tweet_id):
    """
    Writes the latest tweet id to a temp file so the scrape can resume.
    """
    with open('.temp', 'w', encoding='utf-8') as f:
        f.write(str(tweet_id))


def download_tweets(username=None, limit=None, include_replies=False,
                    strip_usertags=False, strip_hashtags=False):
    """Download public Tweets from a given Twitter account
    into a format suitable for training with AI text generation tools.
    :param username: Twitter @ username to gather tweets.
    :param limit: # of tweets to gather; None for all tweets.
    :param include_replies: Whether to include replies to other tweets.
    :param strip_usertags: Whether to remove user tags from the tweets.
    :param strip_hashtags: Whether to remove hashtags from the tweets.
    """

    assert username, "You must specify a username to download tweets from."
    if limit:
        assert limit % 20 == 0, "`limit` must be a multiple of 20."

    # If no limit specifed, estimate the total number of tweets from profile.
    else:
        c_lookup = twint.Config()
        c_lookup.Username = username
        c_lookup.Store_object = True
        c_lookup.Hide_output = True

        twint.run.Lookup(c_lookup)
        limit = twint.output.users_list[0].tweets

    pattern = r'http\S+|pic\.\S+|\xa0|…'

    if strip_usertags:
        pattern += r'|@[a-zA-Z0-9_]+'

    if strip_hashtags:
        pattern += r'|#[a-zA-Z0-9_]+'

    update_resume_file(-1)

    print("Retrieving tweets for @{}...".format(username))

    with open('{}_tweets.csv'.format(username), 'w', encoding='utf8') as f:
        w = csv.writer(f)
        w.writerow(['tweets'])  # gpt-2-simple expects a CSV header by default

        pbar = tqdm(range(limit),
                    desc="Latest Tweet")
        for i in range((limit // 20) - 1):
            tweet_data = []

            # twint may fail; give it up to 5 tries to return tweets
            for _ in range(0, 4):
                if len(tweet_data) == 0:
                    c = twint.Config()
                    c.Store_object = True
                    c.Hide_output = True
                    c.Username = username
                    c.Limit = 40
                    c.Resume = '.temp'

                    c.Store_object_tweets_list = tweet_data

                    twint.run.Search(c)

                    # If it fails, sleep before retry.
                    if len(tweet_data) == 0:
                        sleep(1.0)
                else:
                    continue

            # If still no tweets after multiple tries, we're done
            if len(tweet_data) == 0:
                break

            if i > 0:
                tweet_data = tweet_data[20:]

            if not include_replies:
                tweets = [re.sub(pattern, '', tweet.tweet).strip()
                          for tweet in tweet_data
                          if not is_reply(tweet)]
            else:
                tweets = [re.sub(pattern, '', tweet.tweet).strip()
                          for tweet in tweet_data]

            for tweet in tweets:
                if tweet != '':
                    w.writerow([tweet])

            if i > 0:
                pbar.update(20)
            else:
                pbar.update(40)
            most_recent_tweet = (datetime
                                 .utcfromtimestamp(tweet_data[-1].datetime / 1000.0)
                                 .strftime('%Y-%m-%d %H:%M:%S'))
            pbar.set_description("Latest Tweet: " + most_recent_tweet)

    pbar.close()


if __name__ == "__main__":
    fire.Fire(download_tweets)
