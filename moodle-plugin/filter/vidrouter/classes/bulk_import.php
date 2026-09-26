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

/**
 * Bulk-assigns values onto existing filter_vidrouter_map rows, matched by an existing field.
 *
 * For backfilling a new id onto already-imported courses without touching the schema or
 * reimporting anything.
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class bulk_import
{
    /** @var string[] columns that may be used as the match key */
    public const ASSIGNABLE_FIELDS = [
        'vidkey', 'youtubeid', 'edxvideoid', 'tuddownloadid', 'collegeramaid', 'srtbaseid',
        'urlname', 'courseid', 'title', 'videopagepath',
    ];

    /**
     * Parse pasted CSV text into an array of associative rows, keyed by header name.
     *
     * @param string $csvtext raw CSV, first line must be a header row
     * @return array{header: string[], rows: array[]} header names and parsed data rows
     * @throws \moodle_exception if the header contains an unknown or duplicate column name
     */
    public static function parse_csv(string $csvtext): array
    {
        $lines = preg_split('/\r\n|\r|\n/', trim($csvtext));
        $lines = array_values(array_filter($lines, fn ($l) => trim($l) !== ''));

        if (empty($lines)) {
            throw new \moodle_exception('import_error_empty', 'filter_vidrouter');
        }

        $header = array_map('trim', str_getcsv(array_shift($lines)));
        foreach ($header as $col) {
            if (!in_array($col, self::ASSIGNABLE_FIELDS, true)) {
                throw new \moodle_exception('import_error_unknown_column', 'filter_vidrouter', '', $col);
            }
        }
        if (count($header) !== count(array_unique($header))) {
            throw new \moodle_exception('import_error_duplicate_column', 'filter_vidrouter');
        }

        $rows = [];
        foreach ($lines as $line) {
            $cells = str_getcsv($line);
            $row = [];
            foreach ($header as $i => $col) {
                $row[$col] = isset($cells[$i]) ? trim($cells[$i]) : '';
            }
            $rows[] = $row;
        }

        return ['header' => $header, 'rows' => $rows];
    }

    /**
     * Resolve each parsed row against the DB, without writing anything yet.
     *
     * @param array $rows parsed rows from parse_csv()
     * @param string $matchfield column to look up existing records by
     * @return array[] one plan entry per row: matchvalue, status (matched/unmatched/ambiguous/
     *                 invalid), id (if matched), and changes (columns => new value, if matched)
     */
    public static function plan(array $rows, string $matchfield): array
    {
        global $DB;

        if (!in_array($matchfield, self::ASSIGNABLE_FIELDS, true)) {
            throw new \moodle_exception('import_error_unknown_column', 'filter_vidrouter', '', $matchfield);
        }

        $plan = [];
        foreach ($rows as $row) {
            $matchvalue = $row[$matchfield] ?? '';
            $changes = [];
            foreach ($row as $col => $value) {
                if ($col !== $matchfield && $value !== '') {
                    $changes[$col] = $value;
                }
            }

            if ($matchvalue === '') {
                $plan[] = ['matchvalue' => '', 'status' => 'invalid', 'changes' => $changes];
                continue;
            }

            $existing = $DB->get_records('filter_vidrouter_map', [$matchfield => $matchvalue], '', 'id');

            if (count($existing) === 0) {
                $plan[] = ['matchvalue' => $matchvalue, 'status' => 'unmatched', 'changes' => $changes];
            } elseif (count($existing) > 1) {
                $plan[] = ['matchvalue' => $matchvalue, 'status' => 'ambiguous', 'changes' => $changes];
            } elseif (empty($changes)) {
                $plan[] = ['matchvalue' => $matchvalue, 'status' => 'nochange', 'changes' => $changes];
            } else {
                $plan[] = [
                    'matchvalue' => $matchvalue,
                    'status' => 'matched',
                    'id' => array_key_first($existing),
                    'changes' => $changes,
                ];
            }
        }

        return $plan;
    }

    /**
     * Apply plan; update every 'matched' row, leave everything else alone.
     *
     * @param array[] $plan output of plan()
     * @return int number of rows actually updated
     */
    public static function apply(array $plan): int
    {
        global $DB;

        $updated = 0;
        foreach ($plan as $entry) {
            if ($entry['status'] !== 'matched') {
                continue;
            }
            $record = (object)$entry['changes'];
            $record->id = $entry['id'];
            $record->timemodified = time();
            $DB->update_record('filter_vidrouter_map', $record);
            $updated++;
        }

        if ($updated > 0) {
            $cache = \cache::make('filter_vidrouter', 'map');
            $cache->purge();
        }

        return $updated;
    }
}
