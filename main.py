import logging
import logging.config
import json
from stips_scrapper import StipsScrapping


LOG_CONF = 'logger_conf.ini'

USERNAME = 'your_username'
PASSWORD = 'your_password'

def write_data_to_json(data, out_file):
    with open(out_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def main():
    """
    The main function executes the program:
    A function reads 'hot' messages across all channels and saves the data for each channel in a separate file.
    """
    logging.config.fileConfig(LOG_CONF)
    logging.debug(f'Start')
    sc = StipsScrapping(username=USERNAME, password=PASSWORD)

    links_data = {}
    for channel in sc.channels:
        url = sc.get_channel_url(channel, question_type='hot')
        link = sc.get_links_to_posts(url, scrolls_num=1)
        logging.debug(f'---> channel: {channel}, amount: {len(link)}')
        links_data[channel] = link

    write_data_to_json(links_data, 'data/links_data.json')

    for channel, links in links_data.items():
        logging.debug(f'---> starting to read posts, channel: {channel}')
        ch_data = []
        for i, link in enumerate(links):
            logging.debug(f'link: {i} of {len(links)}')
            posts_data = sc.get_post_data(link)
            ch_data.append(posts_data)


        filename = 'data/data_' + channel + '.json'
        write_data_to_json(ch_data, filename)

    sc.close_driver()


if __name__ == '__main__':
    main()
