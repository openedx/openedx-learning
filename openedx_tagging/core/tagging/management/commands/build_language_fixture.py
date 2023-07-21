"""
Script that downloads all the ISO 639-1 languages and processes them
to write the fixture for the Language system-defined taxonomy.

This function is intended to be used only once,
but can be edited in the future if more data needs to be added to the fixture.
"""
import json
import urllib.request

from django.core.management.base import BaseCommand

endpoint = "https://pkgstore.datahub.io/core/language-codes/language-codes_json/data/97607046542b532c395cf83df5185246/language-codes_json.json"
output = "./openedx_tagging/core/tagging/fixtures/language_taxonomy.yaml"


class Command(BaseCommand):
    def handle(self, **options):
        json_data = self.download_json()
        self.build_fixture(json_data)

    def download_json(self):
        with urllib.request.urlopen(endpoint) as response:
            json_data = response.read()
            return json.loads(json_data)

    def build_fixture(self, json_data):
        tag_pk = -1
        with open(output, "w") as output_file:
            for lang_data in json_data:
                lang_value = self.get_lang_value(lang_data)
                lang_code = lang_data["alpha2"]
                output_file.write("- model: oel_tagging.tag\n")
                output_file.write(f"  pk: {tag_pk}\n")
                output_file.write("  fields:\n")
                output_file.write("    taxonomy: -1\n")
                output_file.write("    parent: null\n")
                output_file.write(f"    value: {lang_value}\n")
                output_file.write(f"    external_id: {lang_code}\n")
                # System tags are identified with negative numbers to avoid clashing with user-created tags.
                tag_pk -= 1
                

    def get_lang_value(self, lang_data):
        """
        Gets the lang value. Some languages has many values.
        """
        lang_list = lang_data["English"].split(";")
        return lang_list[0]
