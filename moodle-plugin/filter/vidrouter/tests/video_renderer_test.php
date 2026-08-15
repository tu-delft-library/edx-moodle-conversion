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
}
