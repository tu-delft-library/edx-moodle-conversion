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
 * Reset the site settings to their defaults.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

require(__DIR__ . '/../../config.php');

$back = new moodle_url('/admin/settings.php', ['section' => 'local_linearnav']);
$PAGE->set_url(new moodle_url('/local/linearnav/reset.php'));
$PAGE->set_context(context_system::instance());
$PAGE->set_pagelayout('admin');
require_admin();

if (!optional_param('confirm', 0, PARAM_BOOL)) {
    $PAGE->set_title(get_string('resetdefaults', 'local_linearnav'));
    echo $OUTPUT->header();
    echo $OUTPUT->confirm(get_string('resetconfirm', 'local_linearnav'), new moodle_url($PAGE->url, ['confirm' => 1]), $back);
    echo $OUTPUT->footer();
    die();
}

require_sesskey();
\local_linearnav\site_settings::reset();
redirect($back, get_string('resetdone', 'local_linearnav'), null, \core\output\notification::NOTIFY_SUCCESS);
