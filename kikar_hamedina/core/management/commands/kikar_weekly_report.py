import StringIO
from optparse import make_option, OptionParser
from time import sleep
import numpy as np

import pandas as pd
from pandas import ExcelWriter

from django.utils import timezone
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.core.management.base import BaseCommand

from core.insights import StatsEngine, Stats, get_times
from mks.models import Party
from facebook_feeds.models import Facebook_Feed, Facebook_Status


def split_by_comma(option, opt, value, parser):
    setattr(parser.values, option.dest, [x.strip() for x in value.split(',')])


class Command(BaseCommand):
    help = "Calculate site stats and email it."

    recipients = make_option('-m',
                             '--mail-recipients',
                             type='string',
                             action='callback',
                             dest='recipients',
                             callback=split_by_comma,
                             help='set emails, seperated by value')

    option_list_helper = list()
    for x in BaseCommand.option_list:
        option_list_helper.append(x)
    option_list_helper.append(recipients)
    option_list = tuple(option_list_helper)

    def feed_and_group_stats(self):
        stats = Stats()
        engine = stats.engine

        feeds = Facebook_Feed.current_feeds.all()

        feeds_data = []
        for feed in feeds:
            num_of_weekly_statuses = engine.n_statuses_last_week([feed.id])
            total_like_count_weekly = engine.total_status_likes_last_week([feed.id])
            mean_like_count_weekly = engine.mean_status_likes_last_week([feed.id])
            mean_comment_count_weekly = engine.mean_status_comments_last_week([feed.id])
            mean_share_count_weekly = engine.mean_status_shares_last_week([feed.id])
            feeds_data.append({'feed_id': feed.id,
                               'feed_name': feed.name or feed.persona.content_object.name,
                               'num_of_weekly_statuses': num_of_weekly_statuses,
                               'total_like_count_this_week': total_like_count_weekly,
                               'mean_like_count_this_week': mean_like_count_weekly,
                               'mean_comment_count_this_week': mean_comment_count_weekly,
                               'mean_share_count_this_week': mean_share_count_weekly,
                               'popularity_count': feed.current_fan_count,
                               'change_since_last_week': feed.popularity_dif(days_back=7,
                                                                             return_value='fan_count_dif_nominal')

            })

        parties_data = list()
        party_ids = dict()
        for party in stats.party_list:
            all_members_for_party = Party.objects.get(id=party.party.id).current_members()
            all_feeds_for_party = [member.facebook_persona.get_main_feed.id for member in
                                   all_members_for_party if member.facebook_persona]
            party_ids[party.party.id] = all_feeds_for_party
            parties_data.append({
                'party_id': party.party.id,
                'party_name': party.party.name,
                'num_of_weekly_statuses': party.n_statuses_last_week,
                'total_like_count_this_week': party.total_status_likes_last_week,
                'mean_like_count_this_week': party.mean_status_likes_last_week,
                'mean_comment_count_this_week': party.mean_status_comments_last_week,
                'mean_share_count_this_week': party.mean_status_shares_last_week,
            })

        factions = [{'id': 1,
                     'name': 'right_side',
                     'feeds': party_ids[14] + party_ids[17],
                     'size': Party.objects.get(id=14).number_of_seats + Party.objects.get(id=17).number_of_seats
                    },
                    {'id': 2,
                     'name': 'center_side',
                     'feeds': party_ids[15] + party_ids[21] + party_ids[25],
                     'size': Party.objects.get(id=15).number_of_seats + Party.objects.get(id=
                                                                                          21).number_of_seats + Party.objects.get(
                         id=25).number_of_seats
                    },
                    {'id': 3,
                     'name': 'left_side',
                     'feeds': party_ids[16] + party_ids[20],
                     'size': Party.objects.get(id=16).number_of_seats + Party.objects.get(id=20).number_of_seats
                    },
                    {'id': 4,
                     'name': 'arab_parties',
                     'feeds': party_ids[22] + party_ids[23] + party_ids[24],
                     'size': Party.objects.get(id=22).number_of_seats + Party.objects.get(
                         id=23).number_of_seats + Party.objects.get(
                         id=24).number_of_seats
                    },
                    {'id': 5,
                     'name': 'charedi_parties',
                     'feeds': party_ids[18] + party_ids[19],
                     'size': Party.objects.get(id=18).number_of_seats + Party.objects.get(id=19).number_of_seats
                    },
        ]

        factions_data = list()
        for fact in factions:
            factions_data.append({
                'faction_id': fact['id'],
                'faction_name': fact['name'],
                'num_of_members_in_faction': fact['size'],
                'num_of_feeds_in_faction': len(fact['feeds']),
                'num_of_weekly_statuses': engine.n_statuses_last_week(fact['feeds']),
                'total_like_count_this_week': engine.total_status_likes_last_week(fact['feeds']),
                'mean_like_count_this_week': engine.mean_status_likes_last_week(fact['feeds']),
                'mean_comment_count_this_week': engine.mean_status_comments_last_week(fact['feeds']),
                'mean_share_count_this_week': engine.mean_status_shares_last_week(fact['feeds']),
            })

        return feeds_data, parties_data, factions_data

    def statuses_data(self):
        week_ago, month_ago = get_times()
        week_statuses = Facebook_Status.objects.filter(published__gte=week_ago, like_count__isnull=False)
        week_statuses_build = [(status.status_id, status.feed.id, status.feed.name, status.published, status.is_deleted,
                                ';'.join([tagged_item.tag.name for tagged_item in
                                          status.tagged_items.filter(tagged_by__username='karineb')]),
                                ';'.join([tagged_item.tag.name for tagged_item in
                                          status.tagged_items.all()]),
                                status.get_link) for
                               status in week_statuses]
        field_names = ['status_id', 'feed_id', 'feed_name', 'published', 'is_deleted', 'tags_by_karine', 'tags', 'link']
        recs = np.core.records.fromrecords(week_statuses_build, names=field_names)
        week_statuses = pd.DataFrame.from_records(recs, coerce_float=True)
        return week_statuses

    def build_and_send_email(self, data, options):
        date = timezone.now().date().strftime('%Y_%m_%d')

        if 'recipients' in options:
            print 'yes'
            recipients = options['recipients']
        else:
            print 'no'
            recipients = settings.DEFAULT_WEEKLY_RECIPIENTS

        print 'recipients:', recipients

        message = EmailMessage(subject='Kikar Hamedina, Weekly Report: %s' % date,
                               body='Kikar Hamedina, Weekly Report: %s.' % date,
                               to=recipients)
        w = ExcelWriter('Weekly_report_%s.xlsx' % date)

        for datum in data:
            # csvfile = StringIO.StringIO()
            pd.DataFrame.from_dict(datum['content']).to_excel(w, sheet_name=datum['name'])

        w.save()
        w.close()
        # f = open(w.path, 'r', encoding='utf-8')
        message.attach_file(w.path)
        message.send()

    def handle(self, *args, **options):

        feeds_data, parties_data, factions_data = self.feed_and_group_stats()
        week_statuses = self.statuses_data()

        all_data = [{'name': 'feeds_data',
                     'content': feeds_data},
                    {'name': 'parties_data',
                     'content': parties_data},
                    {'name': 'factions_data',
                     'content': factions_data},
                    {'name': 'week_statuses',
                     'content': week_statuses}]

        print 'Sending email..'
        self.build_and_send_email(all_data, options)
        print 'Done.'
        # return feeds_data, parties_data, factions_data, week_statuses