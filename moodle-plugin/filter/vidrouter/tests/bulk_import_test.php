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
 * Tests for filter_vidrouter\bulk_import
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @group      filter_vidrouter
 * @covers     \filter_vidrouter\bulk_import
 */
final class bulk_import_test extends \advanced_testcase {

    private function make_row(array $overrides = []): \stdClass {
        global $DB;
        $record = (object)array_merge([
            'vidkey' => 'vid-' . random_string(8),
            'youtubeid' => null,
            'edxvideoid' => null,
            'tuddownloadid' => null,
            'srtbaseid' => null,
            'urlname' => null,
            'courseid' => null,
            'title' => null,
            'videopagepath' => null,
            'timecreated' => time(),
            'timemodified' => time(),
        ], $overrides);
        $record->id = $DB->insert_record('filter_vidrouter_map', $record);
        return $record;
    }

    public function test_parse_csv_reads_header_and_rows(): void {
        $this->resetAfterTest();

        $parsed = bulk_import::parse_csv("youtubeid,edxvideoid\nabc123,uuid-1\ndef456,uuid-2");

        $this->assertSame(['youtubeid', 'edxvideoid'], $parsed['header']);
        $this->assertCount(2, $parsed['rows']);
        $this->assertSame(['youtubeid' => 'abc123', 'edxvideoid' => 'uuid-1'], $parsed['rows'][0]);
        $this->assertSame(['youtubeid' => 'def456', 'edxvideoid' => 'uuid-2'], $parsed['rows'][1]);
    }

    public function test_parse_csv_rejects_unknown_column(): void {
        $this->resetAfterTest();

        $this->expectException(\moodle_exception::class);
        bulk_import::parse_csv("vidkey,notarealcolumn\nabc,123");
    }

    public function test_parse_csv_rejects_duplicate_column(): void {
        $this->resetAfterTest();

        $this->expectException(\moodle_exception::class);
        bulk_import::parse_csv("vidkey,vidkey\nabc,def");
    }

    public function test_parse_csv_rejects_empty_input(): void {
        $this->resetAfterTest();

        $this->expectException(\moodle_exception::class);
        bulk_import::parse_csv("   \n  ");
    }

    public function test_plan_matches_single_row_and_computes_changes(): void {
        $this->resetAfterTest();
        $row = $this->make_row(['youtubeid' => 'abc123']);

        $plan = bulk_import::plan([['youtubeid' => 'abc123', 'edxvideoid' => 'uuid-1']], 'youtubeid');

        $this->assertCount(1, $plan);
        $this->assertSame('matched', $plan[0]['status']);
        $this->assertSame($row->id, $plan[0]['id']);
        $this->assertSame(['edxvideoid' => 'uuid-1'], $plan[0]['changes']);
    }

    public function test_plan_reports_unmatched_when_no_row_found(): void {
        $this->resetAfterTest();

        $plan = bulk_import::plan([['youtubeid' => 'doesnotexist', 'edxvideoid' => 'uuid-1']], 'youtubeid');

        $this->assertSame('unmatched', $plan[0]['status']);
        $this->assertArrayNotHasKey('id', $plan[0]);
    }

    public function test_plan_reports_ambiguous_when_multiple_rows_share_matchvalue(): void {
        $this->resetAfterTest();
        $this->make_row(['youtubeid' => 'dup']);
        $this->make_row(['youtubeid' => 'dup']);

        $plan = bulk_import::plan([['youtubeid' => 'dup', 'edxvideoid' => 'uuid-1']], 'youtubeid');

        $this->assertSame('ambiguous', $plan[0]['status']);
    }

    public function test_plan_reports_invalid_when_matchvalue_is_blank(): void {
        $this->resetAfterTest();

        $plan = bulk_import::plan([['youtubeid' => '', 'edxvideoid' => 'uuid-1']], 'youtubeid');

        $this->assertSame('invalid', $plan[0]['status']);
    }

    public function test_plan_reports_nochange_when_no_other_columns_given(): void {
        $this->resetAfterTest();
        $this->make_row(['youtubeid' => 'abc123']);

        $plan = bulk_import::plan([['youtubeid' => 'abc123', 'edxvideoid' => '']], 'youtubeid');

        $this->assertSame('nochange', $plan[0]['status']);
    }

    public function test_plan_rejects_unknown_matchfield(): void {
        $this->resetAfterTest();

        $this->expectException(\moodle_exception::class);
        bulk_import::plan([['vidkey' => 'x']], 'notarealcolumn');
    }

    public function test_apply_only_updates_matched_rows(): void {
        global $DB;
        $this->resetAfterTest();

        $matched = $this->make_row(['youtubeid' => 'abc123', 'edxvideoid' => null]);
        $untouched = $this->make_row(['youtubeid' => 'other', 'edxvideoid' => null]);

        $plan = bulk_import::plan([
            ['youtubeid' => 'abc123', 'edxvideoid' => 'uuid-1'],
            ['youtubeid' => 'doesnotexist', 'edxvideoid' => 'uuid-2'],
        ], 'youtubeid');
        $updated = bulk_import::apply($plan);

        $this->assertSame(1, $updated);
        $this->assertSame('uuid-1', $DB->get_field('filter_vidrouter_map', 'edxvideoid', ['id' => $matched->id]));
        $this->assertNull($DB->get_field('filter_vidrouter_map', 'edxvideoid', ['id' => $untouched->id]));
    }

    public function test_apply_leaves_columns_not_present_in_the_row_untouched(): void {
        global $DB;
        $this->resetAfterTest();

        $row = $this->make_row(['youtubeid' => 'abc123', 'title' => 'Original title', 'edxvideoid' => null]);

        $plan = bulk_import::plan([['youtubeid' => 'abc123', 'edxvideoid' => 'uuid-1']], 'youtubeid');
        bulk_import::apply($plan);

        $fresh = $DB->get_record('filter_vidrouter_map', ['id' => $row->id]);
        $this->assertSame('Original title', $fresh->title);
        $this->assertSame('uuid-1', $fresh->edxvideoid);
    }

    public function test_apply_purges_the_render_cache_when_something_changed(): void {
        $this->resetAfterTest();
        $this->make_row(['youtubeid' => 'abc123']);

        $cache = \cache::make('filter_vidrouter', 'map');
        $cache->set('somekey', (object) ['stale' => true]);

        $plan = bulk_import::plan([['youtubeid' => 'abc123', 'edxvideoid' => 'uuid-1']], 'youtubeid');
        bulk_import::apply($plan);

        $this->assertFalse($cache->get('somekey'));
    }

    public function test_apply_keeps_the_render_cache_when_nothing_changed(): void {
        $this->resetAfterTest();
        $this->make_row(['youtubeid' => 'abc123']);

        $cache = \cache::make('filter_vidrouter', 'map');
        $cache->set('somekey', (object) ['stale' => true]);

        $plan = bulk_import::plan([['youtubeid' => 'nomatch', 'edxvideoid' => 'uuid-1']], 'youtubeid');
        bulk_import::apply($plan);

        $this->assertNotFalse($cache->get('somekey'));
    }
}
