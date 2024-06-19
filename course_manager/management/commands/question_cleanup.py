from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.utils import timezone

from course_manager.models import Question


class Command(BaseCommand):
    help = "Cleanup question tags"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        questions = Question.objects.all()

        for question in questions:
            print('Removing katex from ', question.id)
            # Check if description needs update
            original_description = question.description
            new_description = self.convert_html(original_description)
            description_updated = new_description != original_description
            if description_updated:
                question.description = new_description

            # Check if options need update
            options_updated = False
            new_options = []
            for option in question.options:
                original_option_description = option['description']
                new_option_description = self.convert_html(original_option_description)
                if new_option_description != original_option_description:
                    option['description'] = new_option_description
                    options_updated = True
                new_options.append(option)

            # Only save if there was an update
            if description_updated or options_updated:
                question.options = new_options  # Assign the updated list back to the options field
                question.updated_at = timezone.now()
                question.save()

    def convert_html(self, html_string):
        soup = BeautifulSoup(html_string, "html.parser")
        for el in soup.select(".ql-formula"):
            math_el = el.find("math")
            if math_el:
                el.replace_with(math_el)
        return str(soup)
