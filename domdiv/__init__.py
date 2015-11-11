from optparse import OptionParser
import os
import codecs
import json

from reportlab.lib.pagesizes import LETTER, A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from cards import Card
from draw import DividerDrawer

LOCATION_CHOICES = ["tab", "body-top", "hide"]
NAME_ALIGN_CHOICES = ["left", "right", "centre", "edge"]
TAB_SIDE_CHOICES = ["left", "right", "left-alternate", "right-alternate", "full"]


def add_opt(options, option, value):
    assert not hasattr(options, option)
    setattr(options, option, value)


def parse_opts(argstring):
    parser = OptionParser()
    parser.add_option("--back_offset", type="float", dest="back_offset", default=0,
                      help="Points to offset the back page to the right; needed for some printers")
    parser.add_option("--back_offset_height", type="float", dest="back_offset_height", default=0,
                      help="Points to offset the back page upward; needed for some printers")
    parser.add_option("--orientation", type="choice", choices=["horizontal", "vertical"],
                      dest="orientation", default="horizontal",
                      help="horizontal or vertical, default:horizontal")
    parser.add_option("--sleeved", action="store_true",
                      dest="sleeved", help="use --size=sleeved instead")
    parser.add_option("--size", type="string", dest="size", default='normal',
                      help="'<%f>x<%f>' (size in cm), or 'normal' = '9.1x5.9', or 'sleeved' = '9.4x6.15'")
    parser.add_option("--minmargin", type="string", dest="minmargin", default="1x1",
                      help="'<%f>x<%f>' (size in cm, left/right, top/bottom), default: 1x1")
    parser.add_option("--papersize", type="string", dest="papersize", default=None,
                      help="'<%f>x<%f>' (size in cm), or 'A4', or 'LETTER'")
    parser.add_option("--tab_name_align", type="choice", choices=NAME_ALIGN_CHOICES + ["center"],
                      dest="tab_name_align", default="left",
                      help="Alignment of text on the tab.  choices: left, right, centre (or center), edge."
                      " The edge option will align the card name to the outside edge of the"
                      " tab, so that when using tabs on alternating sides,"
                      " the name is less likely to be hidden by the tab in front"
                      " (edge will revert to left when tab_side is full since there is no edge in that case);"
                      " default:left")
    parser.add_option("--tab_side", type="choice", choices=TAB_SIDE_CHOICES,
                      dest="tab_side", default="right-alternate",
                      help="Alignment of tab.  choices: left, right, left-alternate, right-alternate, full;"
                      " left/right forces all tabs to left/right side;"
                      " left-alternate will start on the left and then toggle between left and right for the tabs;"
                      " right-alternate will start on the right and then toggle between right and left for the tabs;"  # noqa
                      " full will force all label tabs to be full width of the divider"
                      " default:right-alternate")
    parser.add_option("--tabwidth", type="float", default=4,
                      help="width in cm of stick-up tab (ignored if tab_side is full or tabs-only is used)")
    parser.add_option("--cost", action="append", type="choice",
                      choices=LOCATION_CHOICES, default=[],
                      help="where to display the card cost; may be set to"
                      " 'hide' to indicate it should not be displayed, or"
                      " given multiple times to show it in multiple"
                      " places; valid values are: %s; defaults to 'tab'"
                      % ", ".join("'%s'" % x for x in LOCATION_CHOICES))
    parser.add_option("--set_icon", action="append", type="choice",
                      choices=LOCATION_CHOICES, default=[],
                      help="where to display the set icon; may be set to"
                      " 'hide' to indicate it should not be displayed, or"
                      " given multiple times to show it in multiple"
                      " places; valid values are: %s; defaults to 'tab'"
                      % ", ".join("'%s'" % x for x in LOCATION_CHOICES))
    parser.add_option("--expansions", action="append", type="string",
                      help="subset of dominion expansions to produce tabs for")
    parser.add_option("--cropmarks", action="store_true", dest="cropmarks",
                      help="print crop marks on both sides, rather than tab outlines on one")
    parser.add_option("--linewidth", type="float", default=.1,
                      help="width of lines for card outlines/crop marks")
    parser.add_option("--write_json", action="store_true", dest="write_json",
                      help="write json version of card definitions and extras")
    parser.add_option("--tabs-only", action="store_true", dest="tabs_only",
                      help="draw only tabs to be printed on labels, no divider outlines")
    parser.add_option("--order", type="choice", choices=["expansion", "global"], dest="order",
                      help="sort order for the cards, whether by expansion or globally alphabetical")
    parser.add_option("--expansion_dividers", action="store_true", dest="expansion_dividers",
                      help="add dividers describing each expansion set")
    parser.add_option("--base_cards_with_expansion", action="store_true",
                      help='print the base cards as part of the expansion; ie, a divider for "Silver"'
                      ' will be printed as both a "Dominion" card and as an "Intrigue" card; if this'
                      ' option is not given, all base cards are placed in their own "Base" expansion')
    parser.add_option("--centre_expansion_dividers", action="store_true", dest="centre_expansion_dividers",
                      help='centre the tabs on expansion dividers')
    parser.add_option("--num_pages", type="int", default=-1,
                      help="stop generating after this many pages, -1 for all")
    parser.add_option("--language", default='en_us', help="language of card texts")
    parser.add_option("--include_blanks", action="store_true",
                      help="include a few dividers with extra text")
    parser.add_option("--exclude_events", action="store_true",
                      default=False, help="exclude individual dividers for events")
    parser.add_option("--special_card_groups", action="store_true",
                      default=False, help="group some cards under special dividers (e.g. Shelters, Prizes)")
    parser.add_option("--exclude_prizes", action="store_true",
                      default=False, help="exclude individual dividers for prizes (cornucopia)")
    parser.add_option("--cardlist", type="string", dest="cardlist", default=None,
                      help="Path to file that enumerates each card to be printed on its own line.")
    parser.add_option("--no-tab-artwork", action="store_true", dest="no_tab_artwork",
                      help="don't show background artwork on tabs")
    parser.add_option("--no-card-rules", action="store_true", dest="no_card_rules",
                      help="don't print the card's rules on the tab body")
    parser.add_option("--use-text-set-icon", action="store_true", dest="use_text_set_icon",
                      help="use text/letters to represent a card's set instead of the set icon")
    parser.add_option("--no-page-footer", action="store_true", dest="no_page_footer",
                      help="don't print the set name at the bottom of the page.")
    parser.add_option("--no-card-backs", action="store_true", dest="no_card_backs",
                      help="don't print the back page of the card sheets.")

    options, args = parser.parse_args(argstring)
    if not options.cost:
        options.cost = ['tab']
    if not options.set_icon:
        options.set_icon = ['tab']
    return options, args


def parseDimensions(dimensionsStr):
    x, y = dimensionsStr.upper().split('X', 1)
    return (float(x) * cm, float(y) * cm)


def generate_sample(options):
    import cStringIO
    from wand.image import Image
    buf = cStringIO.StringIO()
    options.num_pages = 1
    generate(options, '.', buf)
    with Image(blob=buf.getvalue()) as sample:
        sample.format = 'png'
        sample.save(filename='sample.png')


def generate(options, data_path, f):
    size = options.size.upper()
    if size == 'SLEEVED' or options.sleeved:
        dominionCardWidth, dominionCardHeight = (9.4 * cm, 6.15 * cm)
        print 'Using sleeved card size, %.2fcm x %.2fcm' % (dominionCardWidth / cm, dominionCardHeight / cm)
    elif size in ['NORMAL', 'UNSLEEVED']:
        dominionCardWidth, dominionCardHeight = (9.1 * cm, 5.9 * cm)
        print 'Using normal card size, %.2fcm x%.2fcm' % (dominionCardWidth / cm, dominionCardHeight / cm)
    else:
        dominionCardWidth, dominionCardHeight = parseDimensions(size)
        print 'Using custom card size, %.2fcm x %.2fcm' % (dominionCardWidth / cm, dominionCardHeight / cm)

    papersize = None
    if not options.papersize:
        if os.path.exists("/etc/papersize"):
            papersize = open("/etc/papersize").readline().upper()
        else:
            papersize = 'LETTER'
    else:
        papersize = options.papersize.upper()

    if papersize == 'A4':
        print "Using A4 sized paper."
        paperwidth, paperheight = A4
    elif papersize == 'LETTER':
        print "Using letter sized paper."
        paperwidth, paperheight = LETTER
    else:
        paperwidth, paperheight = parseDimensions(papersize)
        print 'Using custom paper size, %.2fcm x %.2fcm' % (paperwidth / cm, paperheight / cm)

    cardlist = None
    if options.cardlist:
        print options.cardlist
        cardlist = set()
        with open(options.cardlist) as cardfile:
            for line in cardfile:
                cardlist.add(line.strip())

    if options.orientation == "vertical":
        tabWidth, tabBaseHeight = dominionCardHeight, dominionCardWidth
    else:
        tabWidth, tabBaseHeight = dominionCardWidth, dominionCardHeight

    if options.tab_name_align == "center":
        options.tab_name_align = "centre"

    if options.tab_side == "full" and options.tab_name_align == "edge":
        # This case does not make sense since there are two tab edges in this case.  So picking left edge.
        print >>sys.stderr, "** Warning: Aligning card name as 'left' for 'full' tabs **"
        options.tab_name_align == "left"

    fixedMargins = False
    if options.tabs_only:
        # fixed for Avery 8867 for now
        minmarginwidth = 0.86 * cm   # was 0.76
        minmarginheight = 1.37 * cm   # was 1.27
        tabLabelHeight = 1.07 * cm   # was 1.27
        tabLabelWidth = 4.24 * cm   # was 4.44
        horizontalBorderSpace = 0.96 * cm   # was 0.76
        verticalBorderSpace = 0.20 * cm   # was 0.01
        tabBaseHeight = 0
        tabWidth = tabLabelWidth
        fixedMargins = True
    else:
        minmarginwidth, minmarginheight = parseDimensions(
            options.minmargin)
        if options.tab_side == "full":
            tabLabelWidth = tabWidth
        else:
            tabLabelWidth = options.tabwidth * cm
        tabLabelHeight = .9 * cm
        horizontalBorderSpace = 0 * cm
        verticalBorderSpace = 0 * cm

    tabHeight = tabBaseHeight + tabLabelHeight

    # note: this is convenient, but somewhat inaccurate as the border space
    # isn't actually part of the tab width
    add_opt(options, 'dividerWidth', tabWidth)
    add_opt(options, 'dividerHeight', tabHeight)
    add_opt(options, 'totalTabWidth', tabWidth + horizontalBorderSpace)
    add_opt(options, 'totalTabHeight', tabHeight + verticalBorderSpace)
    add_opt(options, 'labelWidth', tabLabelWidth)
    add_opt(options, 'labelHeight', tabLabelHeight)

    # as we don't draw anything in the final border, it shouldn't count towards how many tabs we can fit
    # so it gets added back in to the page size here
    numTabsVerticalP = int(
        (paperheight - 2 * minmarginheight + verticalBorderSpace) / options.totalTabHeight)
    numTabsHorizontalP = int(
        (paperwidth - 2 * minmarginwidth + horizontalBorderSpace) / options.totalTabWidth)
    numTabsVerticalL = int(
        (paperwidth - 2 * minmarginwidth + verticalBorderSpace) / options.totalTabHeight)
    numTabsHorizontalL = int(
        (paperheight - 2 * minmarginheight + horizontalBorderSpace) / options.totalTabWidth)

    if numTabsVerticalL * numTabsHorizontalL > numTabsVerticalP * numTabsHorizontalP and not fixedMargins:
        add_opt(options, 'numTabsVertical', numTabsVerticalL)
        add_opt(options, 'numTabsHorizontal', numTabsHorizontalL)
        add_opt(options, 'paperheight', paperwidth)
        add_opt(options, 'paperwidth', paperheight)
        add_opt(options, 'minHorizontalMargin', minmarginheight)
        add_opt(options, 'minVerticalMargin', minmarginwidth)
    else:
        add_opt(options, 'numTabsVertical', numTabsVerticalP)
        add_opt(options, 'numTabsHorizontal', numTabsHorizontalP)
        add_opt(options, 'paperheight', paperheight)
        add_opt(options, 'paperwidth', paperwidth)
        add_opt(options, 'minHorizontalMargin', minmarginheight)
        add_opt(options, 'minVerticalMargin', minmarginwidth)

    print "Paper dimensions: {:.2f}cm (w) x {:.2f}cm (h)".format(options.paperwidth / cm,
                                                                 options.paperheight / cm)
    print "Tab dimensions: {:.2f}cm (w) x {:.2f}cm (h)".format(options.totalTabWidth / cm,
                                                               options.totalTabHeight / cm)
    print '{} dividers horizontally, {} vertically'.format(options.numTabsHorizontal,
                                                           options.numTabsVertical)

    if not fixedMargins:
        # dynamically max margins
        add_opt(options, 'horizontalMargin',
                (options.paperwidth -
                 options.numTabsHorizontal * options.totalTabWidth) / 2)
        add_opt(options, 'verticalMargin',
                (options.paperheight -
                 options.numTabsVertical * options.totalTabHeight) / 2)
    else:
        add_opt(options, 'horizontalMargin', minmarginwidth)
        add_opt(options, 'verticalMargin', minmarginheight)

    print "Margins: {:.2f}cm h, {:.2f}cm v\n".format(options.horizontalMargin / cm,
                                                     options.verticalMargin / cm)

    try:
        dirn = os.path.join(data_path, 'fonts')
        pdfmetrics.registerFont(
            TTFont('MinionPro-Regular', os.path.join(dirn, 'MinionPro-Regular.ttf')))
        pdfmetrics.registerFont(
            TTFont('MinionPro-Bold', os.path.join(dirn, 'MinionPro-Bold.ttf')))
        pdfmetrics.registerFont(
            TTFont('MinionPro-Oblique', os.path.join(dirn, 'MinionPro-It.ttf')))
    except:
        raise
        pdfmetrics.registerFont(
            TTFont('MinionPro-Regular', 'OptimusPrincepsSemiBold.ttf'))
        pdfmetrics.registerFont(
            TTFont('MinionPro-Bold', 'OptimusPrinceps.ttf'))

    data_dir = os.path.join(data_path, "card_db", options.language)
    card_db_filepath = os.path.join(data_dir, "cards.json")
    with codecs.open(card_db_filepath, "r", "utf-8") as cardfile:
        cards = json.load(cardfile, object_hook=Card.decode_json)

    language_mapping_filepath = os.path.join(data_dir, "mapping.json")
    with codecs.open(language_mapping_filepath, 'r', 'utf-8') as mapping_file:
        language_mapping = json.load(mapping_file)
        Card.language_mapping = language_mapping

    baseCards = [
        card.name for card in cards if card.cardset.lower() == 'base']

    def isBaseExpansionCard(card):
        return card.cardset.lower() != 'base' and card.name in baseCards

    if options.base_cards_with_expansion:
        cards = [card for card in cards if card.cardset.lower() != 'base']
    else:
        cards = [card for card in cards if not isBaseExpansionCard(card)]

    if options.special_card_groups:
        # Load the card groups file
        card_groups_file = os.path.join(data_dir, "card_groups.json")
        with codecs.open(card_groups_file, 'r', 'utf-8') as cardgroup_file:
            card_groups = json.load(cardgroup_file)
            # pull out any cards which are a subcard, and rename the master card
            new_cards = []
            all_subcards = []
            for subs in [card_groups[x]["subcards"] for x in card_groups]:
                all_subcards += subs
            for card in cards:
                if card.name in card_groups.keys():
                    card.name = card_groups[card.name]["new_name"]
                elif card.name in all_subcards:
                    continue
                new_cards.append(card)
            cards = new_cards

    if options.expansions:
        options.expansions = [o.lower()
                              for o in options.expansions]
        reverseMapping = {
            v: k for k, v in language_mapping.iteritems()}
        options.expansions = [
            reverseMapping.get(e, e) for e in options.expansions]
        filteredCards = []
        knownExpansions = set()
        for c in cards:
            knownExpansions.add(c.cardset)
            if next((e for e in options.expansions if c.cardset.startswith(e)), None):
                filteredCards.append(c)
        unknownExpansions = set(options.expansions) - knownExpansions
        if unknownExpansions:
            print "Error - unknown expansion(s): %s" % ", ".join(unknownExpansions)
            return

        cards = filteredCards

    if options.exclude_events:
        cards = [card for card in cards if not card.isEvent() or card.name == 'Events']

    if options.exclude_prizes:
        cards = [card for card in cards if not card.isPrize()]

    if cardlist:
        cards = [card for card in cards if card.name in cardlist]

    if options.expansion_dividers:
        cardnamesByExpansion = {}
        for c in cards:
            if isBaseExpansionCard(c):
                continue
            cardnamesByExpansion.setdefault(
                c.cardset, []).append(c.name.strip())
        for exp, names in cardnamesByExpansion.iteritems():
            c = Card(
                exp, exp, ("Expansion",), None, ' | '.join(sorted(names)))
            cards.append(c)

    if options.write_json:
        fpath = "cards.json"
        with codecs.open(fpath, 'w', encoding='utf-8') as ofile:
            json.dump(cards,
                      ofile,
                      cls=Card.CardJSONEncoder,
                      ensure_ascii=False,
                      indent=True,
                      sort_keys=True)

    # When sorting cards, want to always put "base" cards after all
    # kingdom cards, and order the base cards in a set order - the
    # order they are listed in the database (ie, all normal treasures
    # by worth, then potion, then all normal VP cards by worth, then
    # trash)
    def baseIndex(name):
        try:
            return baseCards.index(name)
        except Exception:
            return -1

    if options.order == "global":
        sortKey = lambda x: (
            int(x.isExpansion()), baseIndex(x.name), x.name)
    else:
        sortKey = lambda x: (
            x.cardset, int(x.isExpansion()), baseIndex(x.name), x.name)
    cards.sort(key=sortKey)

    if not f:
        f = "dominion_dividers.pdf"

    dd = DividerDrawer()
    dd.draw(f, cards, options)


def main(argstring, data_path):
    options, args = parse_opts(argstring)
    fname = None
    if args:
        fname = args[0]
    return generate(options, data_path, fname)
