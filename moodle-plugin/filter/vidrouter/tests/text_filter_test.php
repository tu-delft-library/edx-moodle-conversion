<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <http://www.gnu.org/licenses/>.

namespace filter_vidrouter;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->libdir . '/filterlib.php');

/**
 * Tests for filter_vidrouter\text_filter through the real filter manager on an activity context.
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @group      filter_vidrouter
 * @covers     \filter_vidrouter\text_filter
 */
final class text_filter_test extends \advanced_testcase {

    private \context $category;
    private \context $course;
    private \context $module;

    protected function setUp(): void {
        parent::setUp();
        $this->resetAfterTest();
        video_renderer::reset_caches();
        \filter_manager::reset_caches();
        filter_set_global_state('vidrouter', TEXTFILTER_ON);

        $category = $this->getDataGenerator()->create_category();
        $course = $this->getDataGenerator()->create_course(['category' => $category->id]);
        $page = $this->getDataGenerator()->create_module('page', ['course' => $course->id]);
        $this->category = \context_coursecat::instance($category->id);
        $this->course = \context_course::instance($course->id);
        $this->module = \context_module::instance($page->cmid);
    }

    private function add_video(string $vidkey, array $ids): void {
        global $DB;
        $DB->insert_record('filter_vidrouter_map', (object) array_merge([
            'vidkey' => $vidkey,
            'title' => 'Video ' . $vidkey,
            'urlname' => $vidkey,
            'timecreated' => time(),
            'timemodified' => time(),
        ], $ids));
        \cache::make('filter_vidrouter', 'map')->purge();
    }

    private function filtered(string $vidkey): string {
        \filter_manager::reset_caches();
        return \filter_manager::instance()->filter_text('[[vid:' . $vidkey . ']]', $this->module);
    }

    public function test_site_defaults_render_youtube_when_no_override(): void {
        $this->add_video('abc', ['youtubeid' => 'yt123']);

        $this->assertStringContainsString('https://www.youtube.com/embed/yt123', $this->filtered('abc'));
    }

    public function test_course_override_disabling_youtube_shows_missing_on_module(): void {
        $this->add_video('abc', ['youtubeid' => 'yt123']);
        filter_set_local_config('vidrouter', $this->course->id, 'primarysource', 'collegeramaid');
        filter_set_local_config('vidrouter', $this->course->id, 'fallbacksource', 'collegeramaid');

        $html = $this->filtered('abc');

        $this->assertStringNotContainsString('youtube.com', $html);
        $this->assertStringContainsString(get_string('videourlmissing', 'filter_vidrouter'), $html);
    }

    public function test_course_override_falls_back_to_youtube(): void {
        $this->add_video('abc', ['youtubeid' => 'yt123']);
        filter_set_local_config('vidrouter', $this->course->id, 'primarysource', 'collegeramaid');
        filter_set_local_config('vidrouter', $this->course->id, 'fallbacksource', 'youtube');

        $this->assertStringContainsString('https://www.youtube.com/embed/yt123', $this->filtered('abc'));
    }

    public function test_course_override_prefers_collegerama_when_both_ids_exist(): void {
        $this->add_video('abc', ['youtubeid' => 'yt123', 'collegeramaid' => 'cg456']);
        filter_set_local_config('vidrouter', $this->course->id, 'primarysource', 'collegeramaid');

        $html = $this->filtered('abc');

        $this->assertStringContainsString('https://collegerama.tudelft.nl/Mediasite/Play/cg456', $html);
        $this->assertStringNotContainsString('youtube.com', $html);
    }

    public function test_category_override_is_inherited_by_module(): void {
        $this->add_video('abc', ['youtubeid' => 'yt123', 'collegeramaid' => 'cg456']);
        filter_set_local_config('vidrouter', $this->category->id, 'primarysource', 'collegeramaid');

        $this->assertStringContainsString('filter_vidrouter_collegerama', $this->filtered('abc'));
    }

    public function test_course_override_beats_category_override(): void {
        $this->add_video('abc', ['youtubeid' => 'yt123', 'collegeramaid' => 'cg456']);
        filter_set_local_config('vidrouter', $this->category->id, 'primarysource', 'collegeramaid');
        filter_set_local_config('vidrouter', $this->course->id, 'primarysource', 'youtube');

        $this->assertStringContainsString('filter_vidrouter_youtube', $this->filtered('abc'));
    }

    public function test_unknown_key_renders_unavailable_placeholder(): void {
        $this->assertStringContainsString('filter_vidrouter_unavailable', $this->filtered('nope'));
    }

    public function test_text_without_shortcode_is_untouched_and_uncached(): void {
        $this->add_video('abc', ['youtubeid' => 'yt123']);
        \filter_manager::reset_caches();

        $out = \filter_manager::instance()->filter_text('<p>plain</p>', $this->module);

        $this->assertSame('<p>plain</p>', $out);
        $this->assertFalse(\cache::make('filter_vidrouter', 'map')->get('abc'));
    }

    public function test_only_referenced_keys_are_cached(): void {
        $this->add_video('a', ['youtubeid' => 'ya']);
        $this->add_video('b', ['youtubeid' => 'yb']);

        $this->filtered('a');

        $cache = \cache::make('filter_vidrouter', 'map');
        $this->assertNotFalse($cache->get('a'));
        $this->assertFalse($cache->get('b'));
    }

    public function test_warm_read_is_served_from_cache(): void {
        global $DB;
        $this->add_video('abc', ['youtubeid' => 'yt123']);
        $this->filtered('abc');

        $DB->delete_records('filter_vidrouter_map', ['vidkey' => 'abc']);

        $this->assertStringContainsString('yt123', $this->filtered('abc'));
    }

    public function test_unknown_key_is_not_cached(): void {
        $this->filtered('nope');

        $this->assertFalse(\cache::make('filter_vidrouter', 'map')->get('nope'));
    }

    public function test_duplicate_and_mixed_keys_all_render(): void {
        $this->add_video('a', ['youtubeid' => 'ya']);
        \filter_manager::reset_caches();

        $out = \filter_manager::instance()->filter_text('[[vid:a]] [[vid:a]] [[vid:nope]]', $this->module);

        $this->assertSame(2, substr_count($out, 'youtube.com/embed/ya'));
        $this->assertStringContainsString('filter_vidrouter_unavailable', $out);
    }

    public function test_purge_picks_up_a_changed_row(): void {
        global $DB;
        $this->add_video('abc', ['youtubeid' => 'old1']);
        $this->filtered('abc');

        $DB->set_field('filter_vidrouter_map', 'youtubeid', 'new2', ['vidkey' => 'abc']);
        \cache::make('filter_vidrouter', 'map')->purge();

        $this->assertStringContainsString('new2', $this->filtered('abc'));
    }
}
