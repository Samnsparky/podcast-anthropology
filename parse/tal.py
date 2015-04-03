import datetime
import json
import requests
import sys

import bs4

START_YEAR = 1995

INDEX_PAGE_TEMPLATE = 'http://www.thisamericanlife.org/radio-archives/%d'
EPISODE_PAGE_TEMPLATE = 'http://www.thisamericanlife.org%s'
DEFAULT_HEADERS = {'User-Agent': 'Digital Anthropology Podcast Crawler'}

USAGE_STR = 'USAGE: python tal.py [json location] [all|new]'

DEBUG = True

MONTH_ABBRV = {
    'Jan': 1,
    'Feb': 2,
    'Mar': 3,
    'Apr': 4,
    'May': 5,
    'Jun': 6,
    'Jul': 7,
    'Aug': 8,
    'Sep': 9,
    'Oct': 10,
    'Nov': 11,
    'Dec': 12
}


# Thanks http://stackoverflow.com/questions/455580
class DateJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        else:
            return super(DateJSONEncoder, self).default(obj)


def enumerate_index_page_locs(start_year=START_YEAR, this_year=None):
    if not this_year: this_year = datetime.date.today().year

    return map(
        lambda year: INDEX_PAGE_TEMPLATE % year,
        range(start_year, this_year+1)
    )


def get_index_pages_raw(start_year=START_YEAR, this_year=None):
    locs = enumerate_index_page_locs(start_year, this_year)
    
    returned_requests = map(
        lambda x: requests.get(x, headers=DEFAULT_HEADERS),
        locs
    )

    successful_requests = filter(
        lambda x: x.status_code == 200,
        returned_requests
    )

    return map(lambda x: x.text, successful_requests)


def get_episode_locs_from_index(content):
    soup = bs4.BeautifulSoup(content)
    episode_list = soup.find_all(class_='episode-archive')
    headers = map(lambda x: x.find('h3'), episode_list)
    links = map(lambda x: x.find('a'), headers)
    valid_links = filter(lambda x: x != None, links)
    local_urls = map(lambda x: x['href'], valid_links)
    global_urls = map(lambda x: EPISODE_PAGE_TEMPLATE % x, local_urls)

    return global_urls


def interpret_date(content):
    components = content.replace(',', '').split(' ')
    month = MONTH_ABBRV[components[0]]
    day = int(components[1])
    year = int(components[2])
    return datetime.date(year, month, day)


def get_episode_info(loc, content):
    soup = bs4.BeautifulSoup(content)

    episode_title = soup.find(class_='node-title').contents[0]
    
    date_str = soup.find(class_='date').contents[0]
    episode_date = interpret_date(date_str)

    tag_sets = soup.findAll(class_ = 'tags')
    tag_set_links = map(lambda x: x.findAll('a'), tag_sets)
    tag_links = [link for links in tag_set_links for link in links]
    tag_names = map(lambda x: x.contents[0].lower(), tag_links)

    return {
        'name': episode_title,
        'date': episode_date,
        'tags': sorted(set(tag_names)),
        'loc': loc
    }


def process_all_episodes():
    if DEBUG:
        print 'downloading index pages...'

    index_pages = get_index_pages_raw()
    episode_location_sets = map(
        lambda x: get_episode_locs_from_index(x),
        index_pages
    )
    episode_locations = set(
        [loc for locs in episode_location_sets for loc in locs]
    )

    if DEBUG:
        print 'downloading episodes...'

    episodes_raw = map(
        lambda x: (x, requests.get(x, headers=DEFAULT_HEADERS).text),
        episode_locations
    )

    if DEBUG:
        print 'parsing episodes...'
    
    episode_info = map(
        lambda (loc, text): get_episode_info(loc, text),
        episodes_raw
    )
    
    return episode_info


def serialize_all_episodes():
    all_episode_info = process_all_episodes()
    return {'episodes': all_episode_info}


def persist_all_episodes(file_location):
    all_episodes = serialize_all_episodes()
    with open(file_location, 'w') as f:
        f.write(
            DateJSONEncoder().encode(all_episodes)
        )


def get_existing_locations_serailized(existing_info):
    return map(lambda x: x['loc'],  existing_info['episodes'])


def update_episode_serialization(existing_info):
    index_pages = get_index_pages_raw()
    episode_location_sets = map(
        lambda x: get_episode_locs_from_index(x),
        index_pages
    )

    episode_locations = [loc for locs in episode_location_sets for loc in locs]
    old_locations = get_existing_locations_serailized(existing_info)
    new_locations = set(episode_locations).difference(old_locations)

    new_episodes_raw = map(
        lambda x: (x, requests.get(x, headers=DEFAULT_HEADERS).text),
        new_locations
    )

    new_episode_info = map(
        lambda (loc, text): get_episode_info(loc, text),
        new_episodes_raw
    )

    existing_info['episodes'].extend(new_episode_info)

    return existing_info


def update_and_persist_episodes(file_location):
    with open(file_location, 'r') as f:
        existing_info = json.load(f)

    updated_info = update_episode_serialization(existing_info)
    with open(file_location, 'w') as f:
        f.write(
            DateJSONEncoder().encode(updated_info)
        )


def main():
    if len(sys.argv) != 3:
        print USAGE_STR
        return

    location = sys.argv[1]

    if sys.argv[2] == 'all':
        persist_all_episodes(location)
    elif sys.argv[2] == 'new':
        update_and_persist_episodes(location)
    else:
        print USAGE_STR


if __name__ == '__main__':
    main()