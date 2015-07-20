# encoding: utf-8

from django.contrib.syndication.views import Feed
from django.core.urlresolvers import reverse
from facebook_feeds.models import Facebook_Status
from core.models import PARTY_MODEL, MEMBER_MODEL
from django.utils import timezone
from django.contrib.syndication.views import FeedDoesNotExist
from django.shortcuts import get_object_or_404
from reporting.models import RSSFeedKeyWord
from django.contrib.auth.models import User
from core.views import SearchView
from django.http.request import HttpRequest

from django.utils.feedgenerator import Rss201rev2Feed

from xml.sax.saxutils import XMLGenerator


class ExtendedRSSFeed(Rss201rev2Feed):
    """
    Create a type of RSS feed that has content:encoded elements.
    """

    #
    # def _unescaped_addQuickElement(self, name, contents=None, attrs=None):
    #     "Convenience method for adding an element with no children"
    #     if attrs is None: attrs = {}
    #     self.startElement(name, attrs)
    #     if contents is not None:
    #         self.characters(contents)
    #     self.endElement(name)

    def root_attributes(self):
        attrs = super(ExtendedRSSFeed, self).root_attributes()
        attrs['xmlns:content'] = 'http://purl.org/rss/1.0/modules/content/'
        return attrs

    # def add_item_elements(self, handler, item):
    #     super(ExtendedRSSFeed, self).add_item_elements(handler, item)
    #     handler.addQuickElement(u'content:encoded', item['content_encoded'])


class LatestStatusesRSSFeed(Feed):
    feed_type = ExtendedRSSFeed

    title = "כיכר המדינה - עדכונים אחרונים"
    link = "http://kikar.org/?range=week"
    description = "העדכונים האחרונים של המועמדים לכנסת ה-20 בפייסבוק, דרך כיכר המדינה"

    def items(self):
        return Facebook_Status.objects.filter(published__gte=timezone.now() - timezone.timedelta(days=7)).order_by(
            '-published')

    def item_title(self, item):
        return u'סטאטוס מאת ח"כ %s, %s' % (item.feed.persona.owner.name, item.feed.persona.owner.current_party.name)


    def item_extra_kwargs(self, item):
        return {'content_encoded': self.item_content_encoded(item)}

    def item_pubdate(self, item):
        return item.published

    description_template = 'rss/default_status_description.html'


    def item_link(self, item):
        return reverse('status-detail', args=[item.status_id])


    def item_content_encoded(self, item):
        content = item.content
        if item.story:
            content += item.story

        # return "<![CDATA[<b>" + content + "</b>]]>"
        return "<b> here" + content + "</b>"

class PartyRSSFeed(Feed):
    description_template = 'rss/party_description.html'

    def get_object(self, request, party_id):
        return get_object_or_404(PARTY_MODEL, pk=party_id)

    def title(self, obj):
        return u"כיכר המדינה - עדכוני רשימה - %s" % obj.name

    def link(self, obj):
        return reverse('party', args=[obj.id])

    def description(self, obj):
        return u"עדכוני פייסבוק של כל המועמדים ברשימה: %s" % obj.name

    def item_link(self, item):
        return reverse('status-detail', args=[item.status_id])

    def items(self, obj):
        return Facebook_Status.objects.filter(
            feed__persona__alt_object_id__in=[x.id for x in MEMBER_MODEL.objects.filter(current_party=obj)]).order_by(
            '-published')[:30]


class KeywordsByUserRSSFeed(Feed):
    description_template = 'rss/party_description.html'

    def get_object(self, request, user_id):
        return get_object_or_404(User, pk=user_id)

    def title(self, obj):
        return u"סטאטוסים שנבחרו למעקב על ידי %s" % obj

    def link(self, obj):
        return '%s/?search_str=%s' % (
            reverse('search'), ','.join([x.keyword for x in obj.words_in_rss_feed.all()]))

    def description(self, obj):
        return u"סטאטוסים המכילים את המילים: %s" % ', '.join([x.keyword for x in obj.words_in_rss_feed.all()])

    def item_title(self, item):
        return u"סטאטוס מאת %s" % item.feed.persona.owner.name

    #
    # def item_link(self, item):
    # return 'kikar.org/%s' % reverse('status-detail', args=[item.status_id])

    def item_pubdate(self, item):
        return item.published

    def item_updateddate(self, item):
        return item.updated

    def item_author_name(self, item):
        return item.feed.persona.owner.name


    def items(self, obj):
        search_view = SearchView(request=HttpRequest())

        Query_Q = search_view.parse_q_object(members_ids=[], parties_ids=[], tags_ids=[],
                                             phrases=[x.keyword for x in obj.words_in_rss_feed.all()])
        return Facebook_Status.objects.filter(Query_Q).order_by('-published')[:30]

