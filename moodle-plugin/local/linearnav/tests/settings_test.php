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
 * Tests for the admin settings.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

use PHPUnit\Framework\Attributes\CoversClass;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->libdir . '/adminlib.php');
require_once($CFG->libdir . '/upgradelib.php');
require_once($CFG->dirroot . '/local/linearnav/db/upgrade.php');

/**
 * Admin settings tests.
 */
#[CoversClass(site_settings::class)]
final class settings_test extends \advanced_testcase {
    public function test_button_text_must_be_quoted(): void {
        $this->resetAfterTest();
        $this->setAdminUser();
        $setting = admin_get_root(true)->locate('local_linearnav')->settings->local_linearnavnextlabel;

        $this->assertTrue($setting->validate('"Next"'));
        $this->assertTrue($setting->validate('" "'));
        $this->assertTrue($setting->validate('""'));
        $this->assertTrue($setting->validate('"<"'));
        $this->assertNotTrue($setting->validate('Next'));
        $this->assertNotTrue($setting->validate(''));
        $this->assertNotTrue($setting->validate('"Next'));
    }

    public function test_reset_restores_defaults(): void {
        $this->resetAfterTest();
        $this->setAdminUser();
        set_config('skiplinked', 0, 'local_linearnav');
        set_config('includetopsections', 1, 'local_linearnav');
        set_config('nextlabel', '" "', 'local_linearnav');

        site_settings::reset();

        $config = get_config('local_linearnav');
        $this->assertSame('1', $config->skiplinked);
        $this->assertSame('0', $config->includetopsections);
        $this->assertSame('"Next"', $config->nextlabel);
        $this->assertSame('"Previous"', $config->prevlabel);
    }

    public function test_upgrade_quotes_labels_and_maps_empty_to_default(): void {
        $this->resetAfterTest();
        set_config('version', 2026112001, 'local_linearnav');
        set_config('prevlabel', '', 'local_linearnav');
        set_config('nextlabel', 'Verder', 'local_linearnav');

        xmldb_local_linearnav_upgrade(2026112001);

        $this->assertSame('"Previous"', get_config('local_linearnav', 'prevlabel'));
        $this->assertSame('"Verder"', get_config('local_linearnav', 'nextlabel'));
    }
}
