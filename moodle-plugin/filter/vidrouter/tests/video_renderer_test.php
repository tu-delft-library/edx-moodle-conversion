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

/**
 * Tests for filter_vidrouter\video_renderer
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @group      filter_vidrouter
 * @covers     \filter_vidrouter\video_renderer
 */
final class video_renderer_test extends \advanced_testcase {

    private function make_record(array $overrides = []): \stdClass {
        return (object)array_merge([
            'title' => 'My Video',
            'urlname' => 'my-video',
            'youtubeid' => null,
            'collegeramaid' => null,
        ], $overrides);
    }

    protected function setUp(): void {
        parent::setUp();
        video_renderer::reset_caches();
    }

    /**
     * @return \context[] category, course and page module contexts, outermost first
     */
    private function make_tree(): array {
        $category = $this->getDataGenerator()->create_category();
        $course = $this->getDataGenerator()->create_course(['category' => $category->id]);
        $page = $this->getDataGenerator()->create_module('page', ['course' => $course->id]);
        return [
            \context_coursecat::instance($category->id),
            \context_course::instance($course->id),
            \context_module::instance($page->cmid),
        ];
    }

    public function test_overrides_for_course_setting_reaches_module_context(): void {
        $this->resetAfterTest();
        [, $course, $module] = $this->make_tree();
        filter_set_local_config('vidrouter', $course->id, 'primarysource', 'collegeramaid');

        $this->assertSame(['primarysource' => 'collegeramaid'], video_renderer::overrides_for($module));
    }

    public function test_overrides_for_category_setting_reaches_course_and_module(): void {
        $this->resetAfterTest();
        [$category, $course, $module] = $this->make_tree();
        filter_set_local_config('vidrouter', $category->id, 'embedstyle', 'video');

        $this->assertSame(['embedstyle' => 'video'], video_renderer::overrides_for($course));
        $this->assertSame(['embedstyle' => 'video'], video_renderer::overrides_for($module));
    }

    public function test_overrides_for_nearest_context_wins(): void {
        $this->resetAfterTest();
        [$category, $course, $module] = $this->make_tree();
        filter_set_local_config('vidrouter', $category->id, 'primarysource', 'youtube');
        filter_set_local_config('vidrouter', $course->id, 'primarysource', 'collegeramaid');

        $this->assertSame('youtube', video_renderer::overrides_for($category)['primarysource']);
        $this->assertSame('collegeramaid', video_renderer::overrides_for($module)['primarysource']);

        video_renderer::reset_caches();
        filter_set_local_config('vidrouter', $module->id, 'primarysource', 'youtube');

        $this->assertSame('youtube', video_renderer::overrides_for($module)['primarysource']);
    }

    public function test_overrides_for_merges_different_settings_across_levels(): void {
        $this->resetAfterTest();
        [$category, $course, $module] = $this->make_tree();
        filter_set_local_config('vidrouter', $category->id, 'primarysource', 'collegeramaid');
        filter_set_local_config('vidrouter', $course->id, 'embedstyle', 'video');

        $this->assertEquals(
            ['primarysource' => 'collegeramaid', 'embedstyle' => 'video'],
            video_renderer::overrides_for($module)
        );
    }

    public function test_overrides_for_is_empty_without_rows(): void {
        $this->resetAfterTest();
        [, , $module] = $this->make_tree();

        $this->assertSame([], video_renderer::overrides_for($module));
    }

    public function test_overrides_for_ignores_unknown_and_empty_values(): void {
        $this->resetAfterTest();
        [, $course, $module] = $this->make_tree();
        filter_set_local_config('vidrouter', $course->id, 'submitbutton', 'Save changes');
        filter_set_local_config('vidrouter', $course->id, 'primarysource', '');

        $this->assertSame([], video_renderer::overrides_for($module));
    }

    public function test_overrides_for_is_cached_until_reset(): void {
        $this->resetAfterTest();
        [, $course, $module] = $this->make_tree();
        filter_set_local_config('vidrouter', $course->id, 'primarysource', 'youtube');
        $this->assertSame('youtube', video_renderer::overrides_for($module)['primarysource']);

        filter_set_local_config('vidrouter', $course->id, 'primarysource', 'collegeramaid');
        $this->assertSame('youtube', video_renderer::overrides_for($module)['primarysource']);

        video_renderer::reset_caches();
        $this->assertSame('collegeramaid', video_renderer::overrides_for($module)['primarysource']);
    }

    public function test_render_uses_youtube_when_available(): void {
        $this->resetAfterTest();
        $record = $this->make_record(['youtubeid' => 'abc123']);

        $html = video_renderer::render($record);

        $this->assertStringContainsString('filter_vidrouter_youtube', $html);
        $this->assertStringContainsString('https://www.youtube.com/embed/abc123', $html);
    }

    public function test_render_falls_back_to_collegerama_when_no_youtube(): void {
        $this->resetAfterTest();
        $record = $this->make_record(['collegeramaid' => 'xyz789']);

        $html = video_renderer::render($record);

        $this->assertStringContainsString('filter_vidrouter_collegerama', $html);
        $this->assertStringContainsString('https://collegerama.tudelft.nl/Mediasite/Play/xyz789', $html);
    }

    public function test_render_shows_missing_when_neither_source_available(): void {
        $this->resetAfterTest();
        $record = $this->make_record();

        $html = video_renderer::render($record);

        $this->assertStringContainsString(get_string('videourlmissing', 'filter_vidrouter'), $html);
    }

    public function test_render_ignores_collegerama_when_fallbacksource_disabled(): void {
        $this->resetAfterTest();
        set_config('fallbacksource', '', 'filter_vidrouter');
        $record = $this->make_record(['collegeramaid' => 'xyz789']);

        $html = video_renderer::render($record);

        $this->assertStringNotContainsString('filter_vidrouter_collegerama', $html);
        $this->assertStringContainsString(get_string('videourlmissing', 'filter_vidrouter'), $html);
    }

    public function test_render_for_export_iframe_style_matches_render(): void {
        $this->resetAfterTest();
        set_config('embedstyle', 'iframe', 'filter_vidrouter');
        $record = $this->make_record(['collegeramaid' => 'xyz789']);

        $this->assertSame(video_renderer::render($record), video_renderer::render_for_export($record));
    }

    public function test_render_for_export_video_style_returns_youtube_link(): void {
        $this->resetAfterTest();
        set_config('embedstyle', 'video', 'filter_vidrouter');
        $record = $this->make_record(['youtubeid' => 'abc123']);

        $html = video_renderer::render_for_export($record);

        $this->assertStringContainsString('https://www.youtube.com/watch?v=abc123', $html);
        $this->assertStringNotContainsString('iframe', $html);
    }

    public function test_render_for_export_video_style_falls_back_to_collegerama_link(): void {
        $this->resetAfterTest();
        set_config('embedstyle', 'video', 'filter_vidrouter');
        $record = $this->make_record(['collegeramaid' => 'xyz789']);

        $html = video_renderer::render_for_export($record);

        $this->assertStringContainsString('https://collegerama.tudelft.nl/Mediasite/Play/xyz789', $html);
        $this->assertStringNotContainsString('iframe', $html);
    }

    public function test_render_for_export_video_style_shows_missing_when_neither_available(): void {
        $this->resetAfterTest();
        set_config('embedstyle', 'video', 'filter_vidrouter');
        $record = $this->make_record();

        $html = video_renderer::render_for_export($record);

        $this->assertStringContainsString(get_string('videourlmissing', 'filter_vidrouter'), $html);
    }

    public function test_render_override_enables_collegerama_when_site_fallback_disabled(): void {
        $this->resetAfterTest();
        set_config('fallbacksource', '', 'filter_vidrouter');
        $record = $this->make_record(['collegeramaid' => 'xyz789']);

        $html = video_renderer::render($record, ['fallbacksource' => 'collegeramaid']);

        $this->assertStringContainsString('filter_vidrouter_collegerama', $html);
    }

    public function test_render_collegerama_primary_beats_youtube_when_both_present(): void {
        $this->resetAfterTest();
        set_config('primarysource', 'collegeramaid', 'filter_vidrouter');
        $record = $this->make_record(['youtubeid' => 'abc123', 'collegeramaid' => 'xyz789']);

        $html = video_renderer::render($record);

        $this->assertStringContainsString('filter_vidrouter_collegerama', $html);
        $this->assertStringNotContainsString('filter_vidrouter_youtube', $html);
    }

    public function test_render_youtube_fallback_used_when_collegerama_primary_has_no_id(): void {
        $this->resetAfterTest();
        set_config('primarysource', 'collegeramaid', 'filter_vidrouter');
        set_config('fallbacksource', 'youtube', 'filter_vidrouter');
        $record = $this->make_record(['youtubeid' => 'abc123']);

        $html = video_renderer::render($record);

        $this->assertStringContainsString('https://www.youtube.com/embed/abc123', $html);
    }

    public function test_render_override_swaps_sources_for_context(): void {
        $this->resetAfterTest();
        $record = $this->make_record(['youtubeid' => 'abc123', 'collegeramaid' => 'xyz789']);

        $html = video_renderer::render($record, ['primarysource' => 'collegeramaid', 'fallbacksource' => 'youtube']);

        $this->assertStringContainsString('filter_vidrouter_collegerama', $html);
    }

    public function test_render_for_export_video_style_honours_collegerama_primary(): void {
        $this->resetAfterTest();
        set_config('embedstyle', 'video', 'filter_vidrouter');
        $record = $this->make_record(['youtubeid' => 'abc123', 'collegeramaid' => 'xyz789']);

        $html = video_renderer::render_for_export($record, ['primarysource' => 'collegeramaid']);

        $this->assertStringContainsString('https://collegerama.tudelft.nl/Mediasite/Play/xyz789', $html);
        $this->assertStringNotContainsString('youtube.com', $html);
    }

    public function test_render_empty_override_falls_back_to_site_setting(): void {
        $this->resetAfterTest();
        set_config('fallbacksource', '', 'filter_vidrouter');
        $record = $this->make_record(['collegeramaid' => 'xyz789']);

        $html = video_renderer::render($record, ['fallbacksource' => '']);

        $this->assertStringNotContainsString('filter_vidrouter_collegerama', $html);
    }

    public function test_render_for_export_override_embedstyle_beats_site_setting(): void {
        $this->resetAfterTest();
        set_config('embedstyle', 'iframe', 'filter_vidrouter');
        $record = $this->make_record(['youtubeid' => 'abc123']);

        $html = video_renderer::render_for_export($record, ['embedstyle' => 'video']);

        $this->assertStringContainsString('https://www.youtube.com/watch?v=abc123', $html);
        $this->assertStringNotContainsString('iframe', $html);
    }

    public function test_render_for_export_override_iframe_beats_site_video_style(): void {
        $this->resetAfterTest();
        set_config('embedstyle', 'video', 'filter_vidrouter');
        $record = $this->make_record(['youtubeid' => 'abc123']);

        $html = video_renderer::render_for_export($record, ['embedstyle' => 'iframe']);

        $this->assertStringContainsString('filter_vidrouter_youtube', $html);
    }
}
