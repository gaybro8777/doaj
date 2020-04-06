from portality.lib.formulaic import Formulaic, FormulaicException
import json

from wtforms import StringField, IntegerField, BooleanField, RadioField, SelectMultipleField, SelectField
from wtforms import widgets
from wtforms.widgets.core import html_params, HTMLString
from portality.formcontext.fields import TagListField

from portality.crosswalks.application_form import ApplicationFormXWalk

FORMS = {
    "contexts" : {
        "public" : {
            "fieldsets" : [
                "public_priority",
                "oac",
                "about",
                "editorial"
            ],
            "asynchronous_warnings" : [
                "all_urls_the_same"
            ],
            "template" : "application_form/public_application.html",
            "crosswalks" : {
                "obj2form" : "portality.formcontext.form_definitions.application_obj2form",
                "form2obj" : "portality.formcontext.form_definitions.application_form2obj"
            },
            "processor" : "portality.formcontext.formcontext.PublicApplication"
        }
    },
    "fieldsets": {
        "oac": {
            "label" : "Open access compliance",
            "fields" : [
                "boai",
                "oa_statement_url"
            ]
        },
        "about" : {
            "label" : "About the journal",
            "fields" : [
                "country",
                "keywords",
                "licensing"
            ]
        },
        "editorial" : {
            "label" : "Editorial",
            "fields" : [
                "submission_time",
                "peer_review",
                "peer_review_other"
            ]
        },
        "public_priority": {
            "label" : "Pre-Qualification Questions",
            "fields" : [
                "boai"
            ],
        }
    },
    "fields": {
        "boai": {
            "label": "DOAJ adheres to the BOAI [definition of open access LINK].  This means that users are"
                "permitted 'to read, download, copy, distribute, print, search, or link to the full texts of articles,"
                "or use them for any other lawful purpose, without financial, legal, or technical barriers other than"
                "those inseparable from gaining access to the internet itself.' Does the journal adhere to this"
                "definition of open access?",
            "input": "checkbox",
            "help": {
                "description": "",
                "tooltip": "For a journal to be indexed in DOAJ, it must fulfil the BOAI definition of open access",
                "doaj_criteria": "You must answer 'Yes'"
            },
            "validate": [
                {"required" : {"message" : "You must check this box to continue"}}
            ],
            "contexts" : {
                "editor" : {
                    "disabled" : True
                },
                "associate_editor" : {
                    "disabled" : True
                }
            }
        },
        "oa_statement_url" : {
            "label" : "What is the URL for the journal's open access statement?",
            "input" : "text",
            "conditional" : [{"field" : "boai", "value" : "y"}],
            "help": {
                "placeholder" : "OA Statement URL",
                "description": "Must start with https://, http://, or www.",
                "tooltip": "Here is an example of a suitable Open Access statement that meets our criteria: "
                        "This is an open access journal which means that all content is freely available without charge" 
                        "to the user or his/her institution. Users are allowed to read, download, copy, distribute," 
                        "print, search, or link to the full texts of the articles, or use them for any other lawful" 
                        "purpose, without asking prior permission from the publisher or the author. This is in accordance"
                        "with the BOAI definition of open access.",
                "doaj_criteria": "You must provide a URL"
            },
            "validate" : [
                "required",
                "is_url"
            ],
            "widgets" : [
                "clickable_url"
            ],
            "attr" : {
                "type" : "url"
            }
        },
        "country" : {
            "label" : "Country of Publisher",
            "input" : "select",
            "options" : "iso_country_list",     # means to get the list from a function
            "multiple" : False,
            "help": {
                "description": "",
                "tooltip": """The country where the publisher carries out its business operations and is registered.""",
            },
            "validate" : [
                "required"
            ],
            "widgets" : [
                {"select" : {}}
            ],
            "contexts" : {
                "editor" : {
                    "disabled" : True
                },
                "associate_editor" : {
                    "disabled" : True
                }
            },
            "attr" : {
                "class" : "input-xlarge"
            }
        },
        "keywords" : {
            "label" : "Add 6 keywords that describe the subject matter of the journal",
            "input" : "taglist",
            "help": {
                "description": "Up to 6 keywords, separated with a comma; must be in English",
                "tooltip": "Only 6 keywords are allowed. Choose words that describe the subject matter of the"
                           "journal and not the journal's qualities. All keywords must be in English.",
            },
            "validate" : [
                "required",
                {"max_tags" : {"max" : 6}},
                "stop_words"
            ],
            "postprocessing" : [
                "to_lower"
            ],
            "widgets" : [
                {
                    "taglist" : {
                        "maximumSelectionSize" : 6,
                        "stopWords" : ["a", "and"]
                    }
                }
            ],
            "attr" : {
                "class" : "input-xlarge"
            },
            "contexts" : {
                "editor" : {
                    "disabled" : True
                },
                "associate_editor" : {
                    "disabled" : True
                }
            }
        },
        "licensing" : {
            "label" : "Indicate which licenses may be applied to the journal content.",
            "input" : "checkbox",
            "options" : [
                {"display" : "CC BY", "value" : "CC BY"},
                {"display" : "CC BY-SA", "value" : "CC BY-SA"},
                {"display" : "CC BY-ND", "value" : "CC BY-ND"},
                {"display" : "CC BY-NC", "value" : "CC BY-NC"},
                {"display" : "CC BY-NC-SA", "value" : "CC BY-NC-SA"},
                {"display" : "CC BY-NC-ND", "value" : "CC BY-NC-ND"},
                {"display" : "CC0", "value" : "CC0"},
                {"display" : "Publisher's own license", "value" : "Publisher's own license", "exclusive" : True},
            ],
            "help": {
                "description": "Select all licenses permitted by this journal.",
                "tooltip": "The journal must use some form of licensing to be considered for indexing in DOAJ. "
                        "If Creative Commons licensing is not used, then select 'Publisher's own license' and enter "
                        "more details below.",
                "doaj_criteria" : "Content must be licenced",
                "seal_criteria" : "Yes: CC BY, CC BY-SA, CC BY-NC"
            },
            "validate" : [
                "required"
            ]
        },
        "submission_time" : {
            "label" : "Average number of weeks between article submission & publication",
            "input" : "number",
            "datatype" : "integer",
            "help": {
                "description": "Enter a number"
            },
            "validate" : [
                "required",
                {"int_range" : {"gte" : 1, "lte" : 100}}
            ],
            "asynchronous_warning" : [
                {"int_range" : {"lte" : 2}}
            ],
            "attr" : {
                "min" : "1",
                "max" : "100"
            }
        },
        "peer_review" : {
            "label" : "What type of peer review is used by the journal?",
            "input" : "checkbox",
            "options" : [
                {"display" : "Editorial review", "value" : "editorial_review"},
                {"display" : "Peer review", "value" : "peer_review"},
                {"display" : "Blind peer review", "value" : "blind_peer_review"},
                {"display" : "Double blind peer review", "value" : "double_blind_peer_review"},
                {"display" : "Post-publication peer review", "value" : "post_publication_peer_review"},
                {"display" : "Open peer review", "value" : "open_peer_review"},
                {"display" : "Other", "value" : "other", "subfields" : ["peer_review_other"]}
            ],
            "help": {
                "description": "Select all that apply",
                "tooltip": """'Editorial review' is only valid for journals in the Humanities""",
                "doaj_criteria" : "Peer review must be carried out"
            },
            "validate" : [
                "required"
            ]
        },
        "peer_review_other": {
            "subfield" : True,
            "input" : "text",
            "help" : {
                "placeholder" : "Other peer review"
            },
            "conditional" : [{"field" : "peer_review", "value" : "other"}],
            "asynchronous_warning" : [
                {"warn_on_value" : {"value" : "None"}}
            ]
        }
    }

}


def iso_country_list():
    from portality.formcontext.choices import Choices
    cl = []
    for v, d in Choices.country():
        cl.append({"display" : d, "value" : v})
    return cl


def render_required(settings, args):
    args["required"] = ""
    if "message" in settings:
        args["data-parsley-required-message"] = settings["message"]


def render_is_url(settings, args):
    args["type"] = "url"


def render_int_range(settings, args):
    args["data-parsley-type"] = "digits"
    if "gte" in settings:
        args["data-parsley-min"] = settings.get("gte")
    if "lte" in settings:
        args["data-parsley-max"] = settings.get("lte")


def application_obj2form(obj):
    return ApplicationFormXWalk.obj2form(obj)


def application_form2obj(form):
    return ApplicationFormXWalk.form2obj(form)


PYTHON_FUNCTIONS = {
    "options" : {
        "iso_country_list" : "portality.formcontext.form_definitions.iso_country_list",
    },
    "validate" : {
        "render" : {
            "required" : "portality.formcontext.form_definitions.render_required",
            "is_url" : "portality.formcontext.form_definitions.render_is_url",
            "int_range" : "portality.formcontext.form_definitions.render_int_range",
        },
        "apply" : {

        }
    },


    "all_urls_the_same" : "portality.formcontext.validators.all_urls_the_same",
    "required_value" : "portality.formcontext.validators.required_value",
    "max_tags" : "portality.formcontext.validators.max_tags",
    "stop_words" : "portality.formcontext.validators.stop_words",
    "to_lower" : "portality.formcontext.postprocessing.to_lower",
    "int_range" : "portality.formcontext.validators.int_range",
    "warn_on_value" : "portality.formcontext.validators.warn_on_value",
    "clickable_url" : "portality.formcontext.widgets.clickable_url",

    "required" : "portality.formcontext.validators.required",
}


JAVASCRIPT_FUNCTIONS = {
    "required_value" : "doaj.forms.validators.requiredValue",
    "required" : "doaj.forms..validators.required",
    "is_url" : "doaj.forms.validators.isUrl",
    "max_tags" : "doaj.forms.validators.maxTags",
    "stop_words" : "doaj.forms.validators.stopWords",
    "int_range" : "doaj.forms.validators.intRange",
    "autocomplete" : "doaj.forms.widgets.autocomplete",

    "clickable_url" : "formulaic.widgets.newClickableUrl",
    "select" : "formulaic.widgets.newSelect",
    "taglist" : "formulaic.widgets.newTagList"
}


class NumberWidget(widgets.Input):
    input_type = 'number'


class ListWidgetWithSubfields(object):
    """
    Renders a list of fields as a `ul` or `ol` list.

    This is used for fields which encapsulate many inner fields as subfields.
    The widget will try to iterate the field to get access to the subfields and
    call them to render them.

    If `prefix_label` is set, the subfield's label is printed before the field,
    otherwise afterwards. The latter is useful for iterating radios or
    checkboxes.
    """
    def __init__(self, html_tag='ul', prefix_label=False):
        assert html_tag in ('ol', 'ul')
        self.html_tag = html_tag
        self.prefix_label = prefix_label

    def __call__(self, field, **kwargs):
        # kwargs.setdefault('id', field.id)
        fl = kwargs.pop("formulaic", None)
        html = ['<%s %s>' % (self.html_tag, html_params(**kwargs))]
        for subfield in field:
            if self.prefix_label:
                html.append('<li>%s %s' % (subfield.label, subfield(**kwargs)))
            else:
                html.append('<li>%s %s' % (subfield(**kwargs), subfield.label))

            if fl is not None:
                sfs = fl.get_subfields(subfield._value())
                for sf in sfs:
                    style = ""
                    if sf.has_conditional:
                        style = " style=display:none "
                    html.append('<span class="{x}_container" {y}>'.format(x=sf.name, y=style))
                    html.append(sf.render_form_control())
                    html.append("</span>")

            html.append("</li>")

        html.append('</%s>' % self.html_tag)
        return HTMLString(''.join(html))


WTFORMS_MAP = [
    {
        "match" : {"input" : "radio"},
        "wtforms" : {"class" : RadioField}
    },
    {
        "match" : {"input" : "checkbox", "options" : True},
        "wtforms" : {"class" : SelectMultipleField, "init" : {"option_widget" : widgets.CheckboxInput, "widget" : ListWidgetWithSubfields}}
    },
    {
        "match" : {"input" : "checkbox", "options" : False},
        "wtforms" : {"class" : BooleanField}
    },
    {
        "match" : {"input" : "select"},
        "wtforms" : {"class" : SelectField}
    },
    {
        "match" : {"input" : "select"},
        "wtforms" : {"class", SelectMultipleField}
    },
    {
        "match" : {"input" : "text"},
        "wtforms" : {"class" : StringField}
    },
    {
        "match" : {"input" : "taglist"},
        "wtforms" : {"class" : TagListField}
    },
    {
        "match" : {"input" : "number", "datatype" : "integer"},
        "wtforms" : {"class": IntegerField, "init" : {"widget" : NumberWidget}}
    }
]

application_form = Formulaic(FORMS, WTFORMS_MAP, function_map=PYTHON_FUNCTIONS, javascript_functions=JAVASCRIPT_FUNCTIONS)


if __name__ == "__main__":
    try:
        c = application_form.context("public")
        print(json.dumps(c._definition, indent=2))
        w = c.wtform()
        for field in w:
            print(field())
    except FormulaicException as e:
        print(e.message)
        raise e