from CTFd.plugins.challenges import BaseChallenge, CHALLENGE_CLASSES
from CTFd.plugins import register_plugin_assets_directory
from CTFd.plugins.keys import get_key_class
from CTFd.models import db, Solves, WrongKeys, Keys, Challenges, Files, Tags, Teams, Awards
from CTFd import utils
import math


class FirstBloodChallenge(BaseChallenge):
    id = "first_blood"  # Unique identifier used to register challenges
    name = "first blood"  # Name of a challenge type
    templates = {  # Handlebars templates used for each aspect of challenge editing & viewing
        'create': '/plugins/FirstBloodChallenge/assets/dynamic-challenge-create.hbs',
        'update': '/plugins/FirstBloodChallenge/assets/dynamic-challenge-update.hbs',
        'modal': '/plugins/FirstBloodChallenge/assets/dynamic-challenge-modal.hbs',
    }
    scripts = {  # Scripts that are loaded when a template is loaded
        'create': '/plugins/FirstBloodChallenge/assets/dynamic-challenge-create.js',
        'update': '/plugins/FirstBloodChallenge/assets/dynamic-challenge-update.js',
        'modal': '/plugins/FirstBloodChallenge/assets/dynamic-challenge-modal.js',
    }

    @staticmethod
    def create(request):
        """
        This method is used to process the challenge creation request.

        :param request:
        :return:
        """
        files = request.files.getlist('files[]')

        # Create challenge
        chal = FirstBloodChallenges(
            name=request.form['name'],
            description=request.form['desc'],
            value=request.form['value'],
            category=request.form['category'],
            type=request.form['chaltype'],
            bonus=request.form['bonus']
        )

        if 'hidden' in request.form:
            chal.hidden = True
        else:
            chal.hidden = False

        max_attempts = request.form.get('max_attempts')
        if max_attempts and max_attempts.isdigit():
            chal.max_attempts = int(max_attempts)

        db.session.add(chal)
        db.session.commit()

        flag = Keys(chal.id, request.form['key'], request.form['key_type[0]'])
        if request.form.get('keydata'):
            flag.data = request.form.get('keydata')
        db.session.add(flag)

        db.session.commit()

        for f in files:
            utils.upload_file(file=f, chalid=chal.id)

        db.session.commit()

    @staticmethod
    def read(challenge):
        """
        This method is in used to access the data of a challenge in a format processable by the front end.

        :param challenge:
        :return: Challenge object, data dictionary to be returned to the user
        """
        challenge = FirstBloodChallenges.query.filter_by(id=challenge.id).first()
        data = {
            'id': challenge.id,
            'name': challenge.name,
            'value': challenge.value,
            'bonus': challenge.bonus,
            'description': challenge.description,
            'category': challenge.category,
            'hidden': challenge.hidden,
            'max_attempts': challenge.max_attempts,
            'type': challenge.type,
            'type_data': {
                'id': FirstBloodChallenge.id,
                'name': FirstBloodChallenge.name,
                'templates': FirstBloodChallenge.templates,
                'scripts': FirstBloodChallenge.scripts,
            }
        }
        return challenge, data

    @staticmethod
    def update(challenge, request):
        """
        This method is used to update the information associated with a challenge. This should be kept strictly to the
        Challenges table and any child tables.

        :param challenge:
        :param request:
        :return:
        """
        challenge = FirstBloodChallenges.query.filter_by(id=challenge.id).first()

        challenge.name = request.form['name']
        challenge.description = request.form['desc']
        challenge.max_attempts = int(request.form.get('max_attempts', 0)) if request.form.get('max_attempts', 0) else 0
        challenge.category = request.form['category']
        challenge.hidden = 'hidden' in request.form

        challenge.value = request.form['value']
        challenge.bonus = request.form['bonus']

        db.session.commit()
        db.session.close()

    @staticmethod
    def delete(challenge):
        """
        This method is used to delete the resources used by a challenge.

        :param challenge:
        :return:
        """
        WrongKeys.query.filter_by(chalid=challenge.id).delete()
        Solves.query.filter_by(chalid=challenge.id).delete()
        Keys.query.filter_by(chal=challenge.id).delete()
        files = Files.query.filter_by(chal=challenge.id).all()
        for f in files:
            utils.delete_file(f.id)
        Files.query.filter_by(chal=challenge.id).delete()
        Tags.query.filter_by(chal=challenge.id).delete()
        FirstBloodChallenges.query.filter_by(id=challenge.id).delete()
        Challenges.query.filter_by(id=challenge.id).delete()
        db.session.commit()

    @staticmethod
    def attempt(chal, request):
        """
        This method is used to check whether a given input is right or wrong. It does not make any changes and should
        return a boolean for correctness and a string to be shown to the user. It is also in charge of parsing the
        user's input from the request itself.

        :param chal: The Challenge object from the database
        :param request: The request the user submitted
        :return: (boolean, string)
        """
        provided_key = request.form['key'].strip()
        chal_keys = Keys.query.filter_by(chal=chal.id).all()
        for chal_key in chal_keys:
            if get_key_class(chal_key.key_type).compare(chal_key.flag, provided_key):
                return True, 'Correct'
        return False, 'Incorrect'

    @staticmethod
    def solve(team, chal, request):
        """
        This method is used to insert Solves into the database in order to mark a challenge as solved.

        :param team: The Team object from the database
        :param chal: The Challenge object from the database
        :param request: The request the user submitted
        :return:
        """
        chal = FirstBloodChallenges.query.filter_by(id=chal.id).first()

        solve_count = Solves.query.join(Teams, Solves.teamid == Teams.id).filter(Solves.chalid==chal.id, Teams.banned==False).count()

        if solve_count == 0:
            name = 'First Blood ({})'.format(chal.name)
            db.session.add(Awards(team.id, name, chal.bonus))

        provided_key = request.form['key'].strip()
        solve = Solves(teamid=team.id, chalid=chal.id, ip=utils.get_ip(req=request), flag=provided_key)
        db.session.add(solve)

        db.session.commit()
        db.session.close()

    @staticmethod
    def fail(team, chal, request):
        """
        This method is used to insert WrongKeys into the database in order to mark an answer incorrect.

        :param team: The Team object from the database
        :param chal: The Challenge object from the database
        :param request: The request the user submitted
        :return:
        """
        provided_key = request.form['key'].strip()
        wrong = WrongKeys(teamid=team.id, chalid=chal.id, ip=utils.get_ip(request), flag=provided_key)
        db.session.add(wrong)
        db.session.commit()
        db.session.close()


class FirstBloodChallenges(Challenges):
    __mapper_args__ = {'polymorphic_identity': 'first_blood'}
    id = db.Column(None, db.ForeignKey('challenges.id'), primary_key=True)
    bonus = db.Column(db.Integer)

    def __init__(self, name, description, value, category, type='dynamic', bonus=50):
        self.name = name
        self.description = description
        self.value = value
        self.bonus = bonus
        self.category = category
        self.type = type


def load(app):
    app.db.create_all()
    CHALLENGE_CLASSES['first_blood'] = FirstBloodChallenge
    register_plugin_assets_directory(app, base_path='/plugins/FirstBloodChallenge/assets/')