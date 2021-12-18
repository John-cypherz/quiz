# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
import random
from quizquestions import QUESTIONS
import logging
import ask_sdk_core.utils as ask_utils

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model import Response
import requests
import os
from ask_sdk_s3.adapter import S3Adapter

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAXLENGTH = 5

s3_adapter = S3Adapter(bucket_name=os.environ["S3_PERSISTENCE_BUCKET"])


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Welcome, say start quiz to begin it right away or say help to get some help."

        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(speak_output)
            .response
        )


class QuizIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("QuizIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        attr = handler_input.attributes_manager.session_attributes
        attr['quiz_score'] = 0
        attr['quiz_questions'] = 1
        attr['state'] = 'quiz'
        slots = handler_input.request_envelope.request.intent.slots
        if (slots['genre'].value):
            genre = slots['genre'].resolutions.resolutions_per_authority[0].values[0].value.id
        else:
            genre = None
        chosen_questions = getQuestions(genre)
        attr['chosen_questions'] = chosen_questions
        question_and_options = get_question_options(1, attr, chosen_questions)
        speak_output = '<say-as interpret-as="interjection">ding ding ding</say-as>.'
        speak_output += '<break time="1s"/>'
        speak_output += 'Lets begin the quiz'
        speak_output += '<break time="1s"/>'
        speak_output += question_and_options
        attr['current_question'] = question_and_options
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(question_and_options)
            .response
        )


class ShowHighScoreHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ShowHighScore")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        attr = handler_input.attributes_manager.session_attributes
        attributes_manager = handler_input.attributes_manager.persistent_attributes
        if 'highscore' in attributes_manager:
            highscore = attributes_manager['highscore']
        else:
            highscore = None
        if(highscore != None):
            speak_output = 'The highscore available is ' + \
                str(highscore) + ' points'
        else:
            speak_output = 'There is no highscore available yet.Say start quiz to begin'

        if(attr.get("state") != "quiz"):
            reprompt = 'You haven\'t started a quiz yet. Say "Start Quiz" to begin.'
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(reprompt)
                .response
            )
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(attr['current_question'])
            .response
        )


class ShowCurrentScoreHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ShowCurrentScore")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        attr = handler_input.attributes_manager.session_attributes
        if(attr.get("state") != "quiz"):
            speak_output = 'You haven\'t started a quiz yet. Say "Start Quiz" to begin.'
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )
        speak_output = 'Your score is ' + str(attr['quiz_score']) + '.'
        speak_output += f' You have {str(MAXLENGTH - attr["quiz_questions"])} questions left'
        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(attr['current_question'])
            .response
        )


class ClearHighScoreHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ClearHighScore")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        attr = handler_input.attributes_manager.session_attributes
        if(attr.get("state") != "quiz"):
            attributes_manager = handler_input.attributes_manager
            attributes_manager.persistent_attributes = {
            }
            attributes_manager.save_persistent_attributes()
            speak_output = 'High score has been cleared.Thank you. '
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask('Say start quiz to begin again')
                .response
            )
        return (
            handler_input.response_builder
            .speak('You can clear high score only when you are not in quiz mode. ')
            .ask(attr['current_question'])
            .response
        )


class AnswerIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        attr = handler_input.attributes_manager.session_attributes
        return (ask_utils.is_intent_name("AnswerIntent")(handler_input) and attr.get("state") == "quiz")

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        attr = handler_input.attributes_manager.session_attributes
        slots = handler_input.request_envelope.request.intent.slots
        option = slots['option'].resolutions.resolutions_per_authority[0].values[0].value.id
        speak_output = f'{show_response_based_on_answer(attr, option)}'
        attr['quiz_questions'] += 1
        if attr['quiz_questions'] > MAXLENGTH:
            speak_output += '<break time="1s"/>'
            speak_output += random_positive_interjection()
            speak_output += '<break time="1s"/>'
            speak_output += 'You have completed the quiz'
            speak_output += '<break time="1s"/>'
            speak_output += 'Your score is '
            speak_output += get_final_applause_music()
            speak_output += str(attr['quiz_score'])+'. '
            speak_output += play_music_on_final_score(attr['quiz_score'])
            speak_output += '<break time="1s"/>'
            speak_output += 'Say "Start Quiz" to begin again. Thanks for playing movie quiz'
            attr['state'] = 'end'
            save_score(attr['quiz_score'], handler_input)
            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )
        else:
            speak_output += '<break time="1s"/>'
            question_and_options = get_question_options(
                attr['quiz_questions'], attr, attr['chosen_questions'])
            speak_output += question_and_options
            attr['current_question'] = question_and_options
            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(question_and_options)
                .response
            )


def save_score(score, handler_input):
    attributes_manager = handler_input.attributes_manager
    persistant_attributes = attributes_manager.persistent_attributes
    if 'highscore' in persistant_attributes:
        highscore = persistant_attributes['highscore']
    else:
        highscore = 0
    attributes_manager.persistent_attributes = {
        'highscore': max(score, highscore)
    }
    attributes_manager.save_persistent_attributes()


def show_response_based_on_answer(attr, chosen_option):
    if str(attr['correct_answer']) == str(chosen_option):
        attr['quiz_score'] += 1
        return f'{get_congratulatory_music()} <amazon:domain name="fun"> {random_positive_interjection()} you have chosen the correct option. <break time="1s"/> Your score is now {attr["quiz_score"] }.  </amazon:domain>'
    else:
        return f'{get_wrong_option_music()} <amazon:domain name="fun"> {random_negative_interjection()}, you have chosen the wrong option. <break time="1s"/> The correct answer is {attr["chosen_questions"][attr["quiz_questions"]-1]["correct_answer"]}.  </amazon:domain>'


def random_positive_interjection():
    interjections = [
        '<say-as interpret-as="interjection">Yeah!</say-as> ',
        '<say-as interpret-as="interjection">Yay!</say-as> ',
        '<say-as interpret-as="interjection">awesome!</say-as> ',
        '<say-as interpret-as="interjection">bazinga!</say-as> ',
        '<say-as interpret-as="interjection">bingo!</say-as> ',
        '<say-as interpret-as="interjection">great!</say-as> ',
    ]
    return random.choice(interjections)


def random_negative_interjection():
    interjections = [
        '<say-as interpret-as="interjection">oops</say-as> ',
        '<say-as interpret-as="interjection">ow</say-as> ',
        '<say-as interpret-as="interjection">sheesh</say-as> ',
        '<say-as interpret-as="interjection">uh uh</say-as> ',
        '<say-as interpret-as="interjection">uh oh</say-as> ',
    ]
    return random.choice(interjections)


def play_music_on_final_score(score):
    if(score > MAXLENGTH/2):
        return get_final_applause_music()
    else:
        return ''


def get_congratulatory_music():
    musics = [
        '<audio src="soundbank://soundlibrary/musical/amzn_sfx_drum_comedy_01"/>',
        '<audio src="soundbank://soundlibrary/musical/amzn_sfx_drum_comedy_02"/>',
        '<audio src="soundbank://soundlibrary/musical/amzn_sfx_drum_comedy_03"/>',
        '<audio src="soundbank://soundlibrary/musical/amzn_sfx_electric_guitar_01"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_applause_05"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_applause_04"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_applause_01"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_applause_02"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_excited_cheer_01"/>'
    ]
    return random.choice(musics)


def get_wrong_option_music():
    musics = [
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_boo_01"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_boo_02"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_boo_03"/>',
        '<audio src="soundbank://soundlibrary/human/hands/hands_02"/>'
    ]
    return random.choice(musics)


def get_final_score_revels():
    music = [
        '<audio src="soundbank://soundlibrary/musical/amzn_sfx_trumpet_bugle_01"/>',
        '<audio src="soundbank://soundlibrary/musical/amzn_sfx_trumpet_bugle_02"/>',
        '<audio src="soundbank://soundlibrary/musical/amzn_sfx_trumpet_bugle_03"/>',
    ]
    return random.choice(music)


def get_final_applause_music():
    musics = [
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_large_crowd_cheer_01"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_large_crowd_cheer_02"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_large_crowd_cheer_03"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_applause_02"/>',
        '<audio src="soundbank://soundlibrary/human/amzn_sfx_crowd_excited_cheer_01"/>'
    ]
    return random.choice(musics)


def get_question_options(question_number, attr, questions):
    return ask_question(question_number, questions) + askOptionsAndSetAnswer(question_number, questions, attr)


def ask_question(position, questions):
    question = f'<say-as interpret-as="interjection"> Here\'s the <say-as interpret-as="ordinal">{position}</say-as> question for you!!</say-as>'
    question += '<break time="1s"/>'
    question += str(questions[position-1]['question'])
    question += '<break time="1s"/>'
    return question


def askOptionsAndSetAnswer(position, questions, attr):
    options = [i for i in questions[position-1]['incorrect_answers']]
    random.shuffle(options)
    correct_answer_position = random.randint(0, 3)
    options.insert(correct_answer_position,
                   questions[position-1]['correct_answer'])
    attr['correct_answer'] = correct_answer_position+1
    for i in range(0, 4):
        options[i] = f' Option {i+1}: {options[i]}'
    return '<break time="1s"/>'.join(options)


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Here are some things you can say: <break time=\"1s\"/>"
        speak_output += "To start the quiz, say start quiz. <break time=\"1s\"/>"
        speak_output += "To know your current score, say 'What's my score'. <break time=\"1s\"/>"
        speak_output += "To know the high score, say 'What's the high score'. <break time=\"1s\"/>"
        speak_output += "To clear the high score, say 'clear high score'. <break time=\"1s\"/>"

        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(speak_output)
            .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Thanks for playing movie quiz! Have a great day"

        return (
            handler_input.response_builder
            .speak(speak_output)
            .response
        )


class FallbackIntentHandler(AbstractRequestHandler):
    """Single handler for Fallback Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")
        speech = "Hmm, I'm not sure. You can say Hello or Help. What would you like to do?"
        reprompt = "I didn't catch that. What can I help you with?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
            .speak(speak_output)
            # .ask("add a reprompt if you want to keep the session open for the user to respond")
            .response
        )


class CatchAllExceptionHandler(AbstractExceptionHandler):

    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(speak_output)
            .response
        )

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


def getQuestions(genre=None):
    questions = []
    if(genre is None):
        questions = QUESTIONS
    else:
        for i in QUESTIONS:
            if(i['category'] == genre):
                questions.append(i)
    chosen_questions = random.sample(QUESTIONS, MAXLENGTH)
    return chosen_questions


sb = CustomSkillBuilder(persistence_adapter=s3_adapter)

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(QuizIntentHandler())
sb.add_request_handler(AnswerIntentHandler())
sb.add_request_handler(ShowCurrentScoreHandler())
sb.add_request_handler(ShowHighScoreHandler())
sb.add_request_handler(ClearHighScoreHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
# make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers
sb.add_request_handler(IntentReflectorHandler())

sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
