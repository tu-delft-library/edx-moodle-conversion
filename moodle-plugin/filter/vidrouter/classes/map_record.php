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
 * Builds a filter_vidrouter_map row from loosely-shaped input (a submitted mform or decoded
 * restore XML), both of which may be missing any of the optional columns.
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class map_record
{
    /**
     * @param object $data source object; missing fields become null
     * @return \stdClass filter_vidrouter_map row, one property per bulk_import::ASSIGNABLE_FIELDS
     */
    public static function build(object $data): \stdClass
    {
        $record = new \stdClass();
        foreach (bulk_import::ASSIGNABLE_FIELDS as $field) {
            $record->$field = $data->$field ?? null;
        }
        return $record;
    }
}
