from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from lxml import etree
import logging
import time
import re
from datetime import datetime


CHANNELS = {'all_questions': 'https://stips.co.il/explore',
            'music': 'https://stips.co.il/channel/%D7%9E%D7%95%D7%A1%D7%99%D7%A7%D7%94',
            'pets': 'https://stips.co.il/channel/%D7%91%D7%A2%D7%9C%D7%99-%D7%97%D7%99%D7%99%D7%9D',
            'study': 'https://stips.co.il/channel/%D7%9C%D7%99%D7%9E%D7%95%D7%93%D7%99%D7%9D',
            'inet_tec': 'https://stips.co.il/channel/%D7%90%D7%99%D7%A0%D7%98%D7%A8%D7%A0%D7%98-%D7%95%D7%98%D7%9B%D7%A0%D7%95%D7%9C%D7%95%D7%92%D7%99%D7%94',
            'movies': 'https://stips.co.il/channel/%D7%A1%D7%93%D7%A8%D7%95%D7%AA-%D7%95%D7%A1%D7%A8%D7%98%D7%99%D7%9D',
            'philosophy': 'https://stips.co.il/channel/%D7%A4%D7%99%D7%9C%D7%95%D7%A1%D7%95%D7%A4%D7%99%D7%94'
            }


class StipsScrapping:
    def __init__(self, username, password):
        self.driver = webdriver.Firefox()
        self.driver.implicitly_wait(30)
        self.scroll_pause_time = 25
        self.page_load_time = 3
        self.channels = CHANNELS
        self.base_url = 'https://stips.co.il'
        self.username = username
        self.password = password
        self._log_in()

    def _log_in(self):
        """ The function logs into website"""
        self.driver.get('https://stips.co.il/login')
        username = self.driver.find_element_by_id('mat-input-1')
        password = self.driver.find_element_by_id('mat-input-2')
        username.send_keys(self.username)
        password.send_keys(self.password)
        button_path = '/html/body/app-full-modal-dialog/div[2]/div/div[2]/app-dynamic-component/app-login-signup/div/div/form/app-button-submit/button'
        self.driver.find_elements_by_xpath(button_path)[0].click()
        logging.debug(f'Logged in to the website')
        time.sleep(self.page_load_time)

        path = "//button[@class='chat mat-icon-button']"
        try:
            self.driver.find_element_by_xpath(path)
        except NoSuchElementException:
            logging.getLogger(__name__).debug(f'Failed to login. Verify username and password')
            self.close_driver()

    def get_channel_url(self, channel, question_type=''):
        """ The function returns a link to the channel """
        if question_type not in ['new', 'hot', '']:
            logging.getLogger(__name__).error('Invalid question type')
            return
        if channel == 'all_questions' and question_type == 'hot':
            question_type += '/today'

        return self.channels[channel] + '/' + question_type

    def get_links_to_posts(self, url, scrolls_num=0):
        """
        The function scrolls page to the end or as scrolls_num of times,
        and returns links for all posts.
        rtype: list os strings
        """
        logging.getLogger(__name__).debug(f'Start to scan links from url: {url}')
        self.driver.get(url)
        # Get scroll height
        last_height = self.driver.execute_script('return document.body.scrollHeight')
        while True:
            # Scroll down to bottom
            self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
            scrolls_num -= 1
            # Wait to load page
            time.sleep(self.scroll_pause_time)
            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script('return document.body.scrollHeight')
            if scrolls_num == 0 or new_height == last_height:
                break
            last_height = new_height

        source = self.driver.page_source
        soup = BeautifulSoup(source, 'lxml')
        elems = soup.find_all('div', {'class': 'item-card ng-star-inserted'})
        links = [self.base_url + BeautifulSoup(str(elem), 'lxml').find('a')['href'] for elem in elems]
        return links

    def get_post_data(self, url):
        """
        The function returns post title, description, post/comment creation time, comments,
        usernames and users id.
        rtype dictionary
        """
        logging.getLogger(__name__).debug(f'Scrapping post : {url}')
        try:
            self.driver.get(url)
            time.sleep(self.page_load_time)
            source = self.driver.page_source
        except TimeoutException:
            logging.getLogger(__name__).debug(f'Failed to load {url}')
            return None

        post_id = re.search(r'ask/(\d+)/', url)
        if post_id:
            post_id = post_id.group(1)
        else:
            logging.getLogger(__name__).debug(f'Failed to get post id, url : {url}')
            return None

        data = [self._get_question_data(source)]
        if data != [None]:
            data.extend(self._get_comments_data(source))

        # Needed for recreation creation time: posts/comments created in the last day are considered
        # from the moment of creation
        now = datetime.now().strftime('%H:%M:%S')
        return {'post_id': post_id, 'scp_time': now, 'data': data}

    @staticmethod
    def _get_profile_data(source):
        """ The function author username and id. """
        user_data = source.find('div', {'class': 'name'})
        user_name = user_data.text
        user_id = None
        user_href = BeautifulSoup(str(user_data), 'lxml').find('a')
        if user_href is not None:
            user_href = re.search(r'/(\d+)$', user_href['href'])
            if user_href:
                user_id = user_href.group(1)
            else:
                logging.getLogger(__name__).debug(f'Failed to get user id, url : {user_href}')

        return user_name, user_id

    def _get_question_data(self, source):
        """
        The function returns dictionary with post title, creation time, description, author username,
        and author id.
        rtype: dictionary
        """
        record = {}
        soup = BeautifulSoup(source, 'lxml')
        data = soup.find('div', {'class': 'title'})
        if data is None:
            return None

        record['data'] = data.text
        description = soup.find('div', {'class': 'text-content ng-star-inserted'})
        if description:
            record['data'] += ' ' + description.text

        user_name, user_id = self._get_profile_data(soup)
        record['user_name'] = user_name
        record['user_id'] = user_id
        record['time'] = soup.find('div', {'class': 'time'}).text
        return record

    def _get_comments_data(self, source):
        """ The function returns list of comments, author username, and author id.
        rtype: list of dictionaries
        """
        comments = []
        path = "//div[@class='ng-star-inserted']/div[@class='item-card ng-star-inserted']"
        elems = etree.HTML(source).xpath(path)
        for elem in elems:
            soup = BeautifulSoup(etree.tostring(elem), 'lxml')
            data = soup.find('div', {'class': 'content ng-star-inserted'}).text
            if data is None:
                continue
            record = {'data': data}
            user_name, user_id = self._get_profile_data(soup)
            record['user_name'] = user_name
            record['user_id'] = user_id
            record['time'] = soup.find('div', {'class': 'time'}).text
            comments.append(record)
        return comments

    def close_driver(self):
        """ The function closes the driver """
        self.driver.quit()
