"""
Site configuration data for config-driven parsers.
Each SiteConfig maps one or more domains to CSS selectors for
table-of-contents links, chapter content, metadata, and cover images.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class SiteConfig:
    site_name: str
    domains: List[str]          # substring match against URL hostname
    toc_selectors: List[str]    # tried in order; should yield <a> tags
    content_selectors: List[str]
    title_selectors: List[str] = field(default_factory=list)
    author_selectors: List[str] = field(default_factory=list)
    description_selectors: List[str] = field(default_factory=list)
    cover_selectors: List[str] = field(default_factory=list)
    # If True this URL IS a single chapter, not a ToC
    single_chapter_url: bool = False


SITE_CONFIGS: List[SiteConfig] = [

    # ------------------------------------------------------------------ FimFiction
    SiteConfig(
        site_name="FimFiction",
        domains=["fimfiction.net"],
        toc_selectors=["ul.chapters a.chapter-title", "ol.chapters a.chapter-title"],
        content_selectors=["div#chapter", "div.bbcode", "div.chapter-content"],
        title_selectors=["a.story_name", "h1.story_name", "h1"],
        author_selectors=["div.info-container a[href*='/user/']", "a.author"],
        description_selectors=["div.description-text", "div.description"],
        cover_selectors=["div.story_container__story_image img", "img.story_image"],
    ),

    # ------------------------------------------------------------------ Creative Novels
    SiteConfig(
        site_name="Creative Novels",
        domains=["creativenovels.com"],
        toc_selectors=[
            "div#chapter_list_novel_page a",
            "div.post_box a",
            "ul.chapter-list a",
        ],
        content_selectors=["div.entry-content.content", "div.entry-content", "article"],
        title_selectors=["header.entry-header h1", "h1.entry-title", "h1"],
        cover_selectors=["img.book_cover", "img.wp-post-image"],
        description_selectors=["div.novel-description", "div.summary__content"],
    ),

    # ------------------------------------------------------------------ FreeWebNovel family
    SiteConfig(
        site_name="FreeWebNovel",
        domains=[
            "freewebnovel.com", "bednovel.com", "innnovel.com",
            "libread.com", "novellive.com", "novellive.app",
            "novellive.net", "readwn.org",
        ],
        toc_selectors=["ul#idData li a", ".m-newest2 ul li a", "ul.chapter-list a"],
        content_selectors=["div.txt", "div#chapter-content", "div.chapter-content"],
        title_selectors=["h1.tit", "h1"],
        author_selectors=["[title=Author] a", "a[href*='author']"],
        description_selectors=["div.desc", "div.intro", "div.summary"],
        cover_selectors=["div.pic img", "div.book-img img", "img.cover"],
    ),

    # ------------------------------------------------------------------ BoxNovel
    SiteConfig(
        site_name="BoxNovel",
        domains=["boxnovel.org", "boxnovel.com"],
        toc_selectors=["ul.list-chapter a", "div.listing-chapters_wrap a"],
        content_selectors=["div#chr-content", "div.text-left", "div.entry-content"],
        title_selectors=["div.post-title h1", "h3.title", "h1"],
        cover_selectors=["div.summary_image img", "div.book img"],
        description_selectors=["div.summary__content", "div.description-summary"],
    ),

    # ------------------------------------------------------------------ AkkNovel
    SiteConfig(
        site_name="AkkNovel",
        domains=["akknovel.com"],
        toc_selectors=["div.chapter-item a", "ul.chapter-list a"],
        content_selectors=["#chr-content", "#chapter-content", "div.chapter-content"],
        title_selectors=["h1"],
        cover_selectors=["div.aspect-h-4 img", "div.book-cover img"],
    ),

    # ------------------------------------------------------------------ FicBook (Russian/international)
    SiteConfig(
        site_name="FicBook",
        domains=["ficbook.net", "fic.fan", "fanfictionero.com", "ficador.com"],
        toc_selectors=["a.part-link", "ul.chapters-list a"],
        content_selectors=["div#content", "article.fanfic-body", "div.fanfic-part"],
        title_selectors=["h1.heading", "h1"],
        author_selectors=["a.creator-username", "a[href*='/authors/']"],
        description_selectors=["div.fanfic-description", "div.description"],
        cover_selectors=["meta[property='og:image']"],
    ),

    # ------------------------------------------------------------------ GoodNovel
    SiteConfig(
        site_name="GoodNovel",
        domains=["goodnovel.com"],
        toc_selectors=["div.catalog-box a", "ul.catalog-list a"],
        content_selectors=[".read-chapter > .read-content", ".read-content", "div.chapter-content"],
        title_selectors=[".bib_info > h1", "h1"],
        author_selectors=[".auth > a", "a.author"],
        description_selectors=[".intro", ".summary"],
        cover_selectors=[".bib_img > img", "img.cover"],
    ),

    # ------------------------------------------------------------------ FictionHunt
    SiteConfig(
        site_name="FictionHunt",
        domains=["fictionhunt.com"],
        toc_selectors=[".chapter-number a", "ul.chapter-list a"],
        content_selectors=["div.StoryChapter__text", "div.chapter-text", "article"],
        title_selectors=["h1"],
        author_selectors=[".Story__meta a"],
    ),

    # ------------------------------------------------------------------ Ficwad
    SiteConfig(
        site_name="Ficwad",
        domains=["ficwad.com"],
        toc_selectors=["ol.toc a", "ul.toc a", "div.toc a"],
        content_selectors=["div#storytext", "div.storytext"],
        title_selectors=["h3 a", "h1", "h2"],
        author_selectors=["a[href^='/profile/']"],
    ),

    # ------------------------------------------------------------------ BeastNovels
    SiteConfig(
        site_name="BeastNovels",
        domains=["beastnovels.com"],
        toc_selectors=["a.chapter-card", "div.chapter-list a"],
        content_selectors=[".chapter-content", "div#chapter-content"],
        title_selectors=["h1"],
        cover_selectors=["img.book-cover", "img.cover"],
    ),

    # ------------------------------------------------------------------ AlicesSW
    SiteConfig(
        site_name="AlicesSW",
        domains=["alicesw.com"],
        toc_selectors=[".tit a", "ul.chapter-list a"],
        content_selectors=[".read-content", "div.chapter-content"],
        title_selectors=[".novel_title", "h1"],
        author_selectors=[".novel_info > p:first-child > a"],
        cover_selectors=[".novel_title img", "img.cover"],
    ),

    # ------------------------------------------------------------------ NHV Novels / Pie Novels
    SiteConfig(
        site_name="NHV/Pie Novels",
        domains=["nhvnovels.com", "pienovels.com"],
        toc_selectors=[".chapter-title a", "ul.chapter-list a"],
        content_selectors=[".chapter-text", "div.chapter-content"],
        title_selectors=[".novel-title", "h1"],
        author_selectors=[".badge-author"],
        cover_selectors=[".novel-image img"],
    ),

    # ------------------------------------------------------------------ EmpireNovel
    SiteConfig(
        site_name="EmpireNovel",
        domains=["empirenovel.com"],
        toc_selectors=["a.chapter_link", "ul.chapter-list a"],
        content_selectors=["#read-novel", "div.chapter-content"],
        title_selectors=["h1:not(.show_title)", "h1"],
        cover_selectors=["div.cover img"],
    ),

    # ------------------------------------------------------------------ CzBooks
    SiteConfig(
        site_name="CzBooks",
        domains=["czbooks.net"],
        toc_selectors=["ul.chapter-list a"],
        content_selectors=[".content", "div#content", "article"],
        title_selectors=[".novel-detail .title", "h1"],
        author_selectors=[".novel-detail span.author a"],
    ),

    # ------------------------------------------------------------------ GoldenNovel
    SiteConfig(
        site_name="GoldenNovel",
        domains=["goldennovel.com"],
        toc_selectors=["div#content-b ul.list a", "ul.chapter-list a"],
        content_selectors=["div.content", "div#content"],
        author_selectors=["span.tip a"],
        cover_selectors=["div.cover img"],
    ),

    # ------------------------------------------------------------------ FictionMania
    SiteConfig(
        site_name="FictionMania",
        domains=["fictionmania.tv"],
        toc_selectors=["table a[href*='xstory']", "table a"],
        content_selectors=["pre", "div.story"],
        title_selectors=["h1", "title"],
    ),

    # ------------------------------------------------------------------ AsianFanfics
    SiteConfig(
        site_name="AsianFanfics",
        domains=["asianfanfics.com"],
        toc_selectors=["aside ul a", "ul.chapter-list a"],
        content_selectors=["div#user-submitted-body", "div.body-text"],
        title_selectors=["h1#story-title", "h1"],
        cover_selectors=["div#bodyText img:first-of-type"],
    ),

    # ------------------------------------------------------------------ ASSTR (Adult Story Text Repository)
    SiteConfig(
        site_name="ASSTR",
        domains=["asstr.org"],
        toc_selectors=["body a[href]"],
        content_selectors=["pre", "body"],
        title_selectors=["title"],
    ),

    # ------------------------------------------------------------------ GameFAQs / GameSpot
    SiteConfig(
        site_name="GameFAQs",
        domains=["gamefaqs.gamespot.com"],
        toc_selectors=[".ftoc a"],
        content_selectors=["#faqwrap", "div.faqtext"],
        title_selectors=["h1"],
        author_selectors=[".contrib-credits a"],
    ),

    # ------------------------------------------------------------------ DeviantArt
    SiteConfig(
        site_name="DeviantArt",
        domains=["deviantart.com"],
        toc_selectors=["div.folderview-art a.torpedo-thumb-link"],
        content_selectors=[
            "div.dev-view-deviation",
            "div[class*='deviation-content']",
            "div[data-hook='deviation_std_literature']",
        ],
        title_selectors=["div.folderview-top h1", "h1"],
        author_selectors=["a.username", "a[data-hook='deviation_user_link']"],
        cover_selectors=["img.dev-content-full", "img[fetchpriority='high']"],
    ),

    # ------------------------------------------------------------------ AthenaTLS
    SiteConfig(
        site_name="AthenaTLS",
        domains=["athenatls.com"],
        toc_selectors=[".chapter-list a", "ul.chapters a"],
        content_selectors=["div.chapter-text-content", "div.entry-content"],
        title_selectors=["h1"],
    ),

    # ------------------------------------------------------------------ Foxaholic
    SiteConfig(
        site_name="Foxaholic",
        domains=["foxaholic.com"],
        toc_selectors=[".chapter-link a", "li.wp-manga-chapter a"],
        content_selectors=[".chapter-content", ".reading-content", "div.entry-content"],
        title_selectors=["h1"],
        cover_selectors=[".summary_image img", "img.img-responsive"],
        description_selectors=[".summary__content"],
    ),

    # ------------------------------------------------------------------ Chrysanthemum Garden (BL/Danmei TLs)
    SiteConfig(
        site_name="Chrysanthemum Garden",
        domains=["chrysanthemumgarden.com"],
        toc_selectors=["li.chapter a", "ul.table_of_contents a", "div.chapter-listing a"],
        content_selectors=["div#content", "article.post-content", "div.entry-content"],
        title_selectors=["h1", "h2.title"],
        author_selectors=["a.author"],
        cover_selectors=["img.attachment-post-thumbnail"],
    ),

    # ------------------------------------------------------------------ Exiled Rebels Scanlations
    SiteConfig(
        site_name="Exiled Rebels Scanlations",
        domains=["exiledrebelsscanlations.com"],
        toc_selectors=["li.wp-manga-chapter a", "ul.main.version-chap a"],
        content_selectors=["div.reading-content", "div.entry-content"],
        title_selectors=["h1"],
        cover_selectors=[".summary_image img"],
    ),

    # ------------------------------------------------------------------ Active Translations
    SiteConfig(
        site_name="Active Translations",
        domains=["activetranslations.xyz"],
        toc_selectors=["li.wp-manga-chapter a", "div.chapter-list a"],
        content_selectors=["div.reading-content", "div.entry-content"],
        title_selectors=["h1"],
        cover_selectors=[".summary_image img"],
    ),

    # ------------------------------------------------------------------ Aerial Rain (WP translation blog)
    SiteConfig(
        site_name="Aerial Rain",
        domains=["aerialrain.com"],
        toc_selectors=["li.wp-manga-chapter a", "div.listing-chapters_wrap a"],
        content_selectors=["div.reading-content", "div.entry-content"],
        title_selectors=["h1"],
        cover_selectors=[".summary_image img"],
    ),

    # ------------------------------------------------------------------ Asian Hobbyist
    SiteConfig(
        site_name="Asian Hobbyist",
        domains=["asianhobbyist.com"],
        toc_selectors=["li.wp-manga-chapter a", "div.chapter-list a"],
        content_selectors=["div.reading-content", "div.entry-content"],
        title_selectors=["h1"],
        cover_selectors=[".summary_image img"],
    ),

    # ------------------------------------------------------------------ Flying Lines (Scanlation)
    SiteConfig(
        site_name="Flying Lines",
        domains=["flying-lines.com"],
        toc_selectors=["li.chapter-item a", "div.chapter-list a"],
        content_selectors=["div.chapter-content", "div.read-content"],
        title_selectors=["h1"],
        cover_selectors=["img.book-cover"],
    ),

    # ------------------------------------------------------------------ Crimson Translations
    SiteConfig(
        site_name="Crimson Translations",
        domains=["crimsontranslations.com"],
        toc_selectors=["li.wp-manga-chapter a", "div.chapters-list a"],
        content_selectors=["div.reading-content", "div.entry-content"],
        title_selectors=["h1"],
        cover_selectors=[".summary_image img"],
    ),

    # ------------------------------------------------------------------ Dark Novels
    SiteConfig(
        site_name="Dark Novels",
        domains=["darknovels.com"],
        toc_selectors=["li.wp-manga-chapter a", "ul.chapter-list a"],
        content_selectors=["div.reading-content", "div.entry-content"],
        title_selectors=["h1"],
        cover_selectors=[".summary_image img"],
    ),

    # ------------------------------------------------------------------ Chyoa (Interactive Fiction)
    SiteConfig(
        site_name="Chyoa",
        domains=["chyoa.com"],
        toc_selectors=["div.chapter-list a[href*='/chapter/']"],
        content_selectors=["div.story-text", "div.chapter-text"],
        title_selectors=["h1", "h2.story-title"],
        author_selectors=["a.author"],
        cover_selectors=["img.cover-image"],
    ),

    # ------------------------------------------------------------------ FanFic Paradise
    SiteConfig(
        site_name="FanFic Paradise",
        domains=["fanficparadise.com"],
        toc_selectors=["ul.chapter-list a", "div.chapter-list a"],
        content_selectors=["div.chapter-content", "div#chapter"],
        title_selectors=["h1"],
        author_selectors=["a.author"],
    ),

    # ------------------------------------------------------------------ Eng Novel
    SiteConfig(
        site_name="Eng Novel",
        domains=["engnovel.com"],
        toc_selectors=["ul.chapter-list a", "li.chapter-item a"],
        content_selectors=["div.chapter-content", "div#chapter-content"],
        title_selectors=["h1"],
        cover_selectors=["div.book-image img"],
    ),

    # ------------------------------------------------------------------ Full Novel
    SiteConfig(
        site_name="Full Novel",
        domains=["fullnovel.co"],
        toc_selectors=["ul.chapter-list a"],
        content_selectors=[".chapter-content", "div#chapter-content"],
        title_selectors=["h1"],
        cover_selectors=["main img:first-child"],
    ),

    # ------------------------------------------------------------------ Wuxia Click / Wuxia World EU variants
    SiteConfig(
        site_name="WuxiaClick",
        domains=["wuxiaclick.com", "wuxiaworld.eu"],
        toc_selectors=["ul.chapter-list a", "li.chapter-item a"],
        content_selectors=["div.chapter-content", "div#chapter-content", "div.entry-content"],
        title_selectors=["h1"],
        cover_selectors=["img.book-cover"],
        description_selectors=["div.description", "div.summary"],
    ),

    # ------------------------------------------------------------------ Diurnis
    SiteConfig(
        site_name="Diurnis",
        domains=["diurnis.com"],
        toc_selectors=["div.chapter-list a", "ul.chapters a"],
        content_selectors=["div.chapter-content", "article"],
        title_selectors=["h1"],
    ),

    # ------------------------------------------------------------------ Betwixtedbutterfly (Elementor WP)
    SiteConfig(
        site_name="Betwixtedbutterfly",
        domains=["betwixtedbutterfly.com"],
        toc_selectors=["div.elementor-widget-container a[href*='chapter']"],
        content_selectors=["div.elementor-widget-text-editor", "div.entry-content"],
        title_selectors=["h1"],
    ),

    # ------------------------------------------------------------------ FoxTeller
    SiteConfig(
        site_name="FoxTeller",
        domains=["foxteller.com"],
        toc_selectors=["a.chapter-link", "div.chapter-list a"],
        content_selectors=["div.chapter-text", "div.content"],
        title_selectors=["h1"],
        author_selectors=["a.author-name"],
        cover_selectors=["img.cover"],
    ),

    # ------------------------------------------------------------------ FastNovel (may be down)
    SiteConfig(
        site_name="FastNovel",
        domains=["fastnovel.net", "novelgate.net"],
        toc_selectors=["div#list-chapters li a"],
        content_selectors=["div#chapter-body"],
        title_selectors=["div.film-info h1"],
        author_selectors=["div.film-info ul.meta-data a"],
        cover_selectors=["div.book-cover img[data-original]"],
    ),

    # ------------------------------------------------------------------ Crush Novel
    SiteConfig(
        site_name="Crush Novel",
        domains=["crushnovel.com"],
        toc_selectors=["ul.chapter-list a", "div.chapter-list a"],
        content_selectors=["div.chapter-content", "#chapter-content"],
        title_selectors=["h1"],
        cover_selectors=["img.book-cover"],
    ),

    # ------------------------------------------------------------------ Fictionread
    SiteConfig(
        site_name="FictionRead",
        domains=["fictionread.net"],
        toc_selectors=["ul.chapter-list a", "li.chapter a"],
        content_selectors=["div.chapter-content", "div.read-content"],
        title_selectors=["h1"],
        cover_selectors=["img.cover"],
    ),


]
