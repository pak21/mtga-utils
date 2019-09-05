from __future__ import print_function
from future.utils import iteritems
import os
import simplejson as json
from mtga.set_data import all_mtga_cards
import scryfall

def _mtga_file_path(filename):
    """Get the full path to the specified MTGA file"""
    appdata = os.getenv("APPDATA")
    # If we don't have APPDATA, assume we're in the user's home directory
    base = [appdata, ".."] if appdata else ["AppData"]
    components = base + ["LocalLow", "Wizards of the Coast", "MTGA", filename]
    return os.path.join(*components)

MTGA_COLLECTION_KEYWORD = "PlayerInventory.GetPlayerCardsV3"
MTGA_WINDOWS_LOG_FILE = _mtga_file_path("output_log.txt")
MTGA_WINDOWS_FORMATS_FILE = _mtga_file_path("formats.json")

class MtgaLogParsingError(ValueError):
    """Exception raised when parsing json data fails"""
    pass


class MtgaUnknownCard(ValueError):
    """Exception when card is not found in python-mtga package"""
    pass


class MtgaLog(object):
    """Process MTGA/Unity log file"""

    def __init__(self, log_filename):
        self.log_filename = log_filename
        self.fallback = True

    def scryfall_fallback(self, fallback=True):
        """Enable/disable fallback to Scryfall"""
        self.fallback = fallback

    def get_last_keyword_block(self, keyword):
        """Find json block for specific keyword (last in the file)
        Args:
            keyword (str): Keyword to search for in the log file
        Returns: list
        """
        bucket = []
        copy = False
        levels = 0
        with open(self.log_filename) as logfile:
            for line in logfile:
                if copy:
                    bucket.append(line)

                if line.find(keyword) > -1:
                    bucket = []
                    copy = True

                levels += line.count('{')
                levels -= line.count('}')

                if line.count('}') > 0 and levels == 0:
                    copy = False
        return bucket

    def get_last_json_block(self, keyword):
        """Get the block as dict"""
        try:
            block = self.get_last_keyword_block(keyword)
            return self._list_to_json(block)
        except ValueError as exception:
            raise MtgaLogParsingError(exception)
            #return False

    def _list_to_json(self, json_list):
        json_string = ''.join(json_list)
        return json.loads(json_string)

    def _fetch_card_from_scryfall(self, mtga_id):
        if not self.fallback:
            return None
        try:
            card = scryfall.get_mtga_card(mtga_id)
        except Exception as scryfall_error:
            card = scryfall.ScryfallError(scryfall_error)
        return card

    def get_collection(self):
        """Generator for MTGA collection"""
        collection = self.get_last_json_block('<== ' + MTGA_COLLECTION_KEYWORD)
        for (mtga_id, count) in iteritems(collection):
            try:
                card = all_mtga_cards.find_one(mtga_id)
            except ValueError as exception:
                yield [mtga_id, MtgaUnknownCard(exception), count]
                #Card not found, try to get it from scryfall
                card = self._fetch_card_from_scryfall(mtga_id)

            if card is not None:
                yield [mtga_id, card, count]



class MtgaFormats(object):
    """Process MTGA/Unity formats file"""

    def __init__(self, formats_filename):
        self.formats_filename = formats_filename

    def _get_formats_json(self):
        """Gets the formats json"""
        with open(self.formats_filename) as formats_file:
            return json.load(formats_file)

    def get_format_sets(self, mtg_format):
        """Returns list of current sets in standard format"""
        try:
            json_data = self._get_formats_json()
        except ValueError as exception:
            raise MtgaLogParsingError(exception)

        sets = []
        for item in json_data:
            if item.get("name").lower() == str(mtg_format):
                for mtga_set in item.get("sets"):
                    sets.append(mtga_set)
                    if mtga_set == "DAR":
                        sets.append("DOM")
        return sets

    def get_set_info(self, mtga_set):
        return scryfall.get_set_info(mtga_set)

    def get_set_card_count(self, mtga_set):
        set_info = self.get_set_info(mtga_set)
        return set_info.get('card_count', 0)
