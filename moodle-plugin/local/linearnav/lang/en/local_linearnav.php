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

/**
 * Language strings.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$string['disclaimer'] = 'The plugin walks through anything you can see in the sidebar. Make sure that you are viewing as a student '
    . 'if you have \'Skip linked and hidden pages\' off.';
$string['heading_buttons'] = 'Buttons';
$string['heading_order'] = 'Order';
$string['heading_skipping'] = 'Skipping logic';
$string['heading_stops'] = 'Section stops';
$string['includesubsections'] = 'Subsections';
$string['includesubsections_desc'] = 'Stop at each subsection page.';
$string['includetopsections'] = 'Top-level sections';
$string['includetopsections_desc'] = 'Stop at each top-level section page.';
$string['next'] = 'Next';
$string['nextlabel'] = 'Next button text';
$string['nextlabel_desc'] = 'Text on the Next button in double quotes, e.g. "Next", " " or "". Any characters.';
$string['pluginname'] = 'Linear navigation';
$string['previous'] = 'Previous';
$string['prevlabel'] = 'Previous button text';
$string['prevlabel_desc'] = 'Text on the Previous button in double quotes, e.g. "Previous", " " or "". Any characters.';
$string['privacy:metadata'] = 'The linear navigation plugin does not store any personal data.';
$string['resetconfirm'] = 'Put all linear navigation site settings back to their defaults? Course overrides are kept.';
$string['resetdefaults'] = 'Reset to defaults';
$string['resetdone'] = 'Linear navigation settings reset to their defaults.';
$string['sectionorder'] = 'Section order';
$string['sectionorder_auto'] = 'Automatic';
$string['sectionorder_core'] = 'Moodle subsections only';
$string['sectionorder_desc'] = 'How nested sections are walked. Automatic follows the parent and order of formats like '
    . 'Authora when a course has them, otherwise subsection activities. Only change this if the walk does not match '
    . 'the sidebar.';
$string['sectionorder_tree'] = 'Format tree';
$string['sectionorder_treedesc'] = 'Format tree, siblings reversed';
$string['skipfiles'] = 'Skip files';
$string['skipfiles_desc'] = 'Leave file activities out of the walk. When off, a file opens its own page with a '
    . 'download link.';
$string['skiplinked'] = 'Skip linked and hidden pages';
$string['skiplinked_desc'] = 'Leave out link activities that point at a page in the course, and everything in hidden sections.';
$string['skiptargets'] = 'Include target of links in skipping';
$string['skiptargets_desc'] = 'When off, original pages stay in the walk.';
$string['usesitedefault'] = 'Use site default';
