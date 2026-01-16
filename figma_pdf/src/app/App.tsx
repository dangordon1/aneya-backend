import { useState } from 'react';
import { Activity } from 'lucide-react';
import { Input } from '@/app/components/ui/input';
import { Textarea } from '@/app/components/ui/textarea';
import { Label } from '@/app/components/ui/label';

interface PregnancyRecord {
  no: number;
  modeOfConception: string;
  modeOfDelivery: string;
  sexAge: string;
  aliveDead: string;
  abortion: string;
  birthWt: string;
  year: string;
  breastFeeding: string;
  anomalies: string;
}

export default function App() {
  const [pregnancyRecords] = useState<PregnancyRecord[]>([
    {
      no: 1,
      modeOfConception: '',
      modeOfDelivery: '',
      sexAge: '',
      aliveDead: '',
      abortion: '',
      birthWt: '',
      year: '',
      breastFeeding: '',
      anomalies: '',
    },
    {
      no: 2,
      modeOfConception: '',
      modeOfDelivery: '',
      sexAge: '',
      aliveDead: '',
      abortion: '',
      birthWt: '',
      year: '',
      breastFeeding: '',
      anomalies: '',
    },
    {
      no: 3,
      modeOfConception: '',
      modeOfDelivery: '',
      sexAge: '',
      aliveDead: '',
      abortion: '',
      birthWt: '',
      year: '',
      breastFeeding: '',
      anomalies: '',
    },
  ]);

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-5xl mx-auto bg-white shadow-lg">
        {/* Letterhead */}
        <div className="bg-[#0c3555] text-white px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-[#1d9e99] rounded-full flex items-center justify-center">
                <Activity className="w-10 h-10" />
              </div>
              <div>
                <h1 className="text-white">Medical Center Name</h1>
                <p className="text-sm text-[#f6f5ee]/80">123 Healthcare Avenue, City, State 12345</p>
                <p className="text-sm text-[#f6f5ee]/80">Phone: (555) 123-4567 | Fax: (555) 123-4568</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-[#f6f5ee]/80">Date: ______________</p>
              <p className="text-sm text-[#f6f5ee]/80">File No: ______________</p>
            </div>
          </div>
        </div>

        {/* Report Card Content */}
        <div className="p-8 space-y-6">
          {/* Patient Information Header */}
          <div className="border-b-2 border-[#1d9e99] pb-4">
            <h2 className="text-[#0c3555] mb-4">PATIENT REPORT CARD</h2>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="patientName" className="text-[#0c3555]">Patient Name</Label>
                <Input id="patientName" className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]" />
              </div>
              <div>
                <Label htmlFor="patientId" className="text-[#0c3555]">Patient ID</Label>
                <Input id="patientId" className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]" />
              </div>
              <div>
                <Label htmlFor="dob" className="text-[#0c3555]">Date of Birth</Label>
                <Input id="dob" type="date" className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]" />
              </div>
              <div>
                <Label htmlFor="age" className="text-[#0c3555]">Age</Label>
                <Input id="age" type="number" className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]" />
              </div>
            </div>
          </div>

          {/* Vital Statistics - Numerical Fields */}
          <div>
            <h3 className="text-[#0c3555] mb-3 pb-2 border-b border-[#1d9e99]">Vital Statistics</h3>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <Label htmlFor="height" className="text-[#0c3555]">Height (cm)</Label>
                <Input
                  id="height"
                  type="number"
                  step="0.1"
                  placeholder="170.5"
                  className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]"
                />
              </div>
              <div>
                <Label htmlFor="weight" className="text-[#0c3555]">Weight (kg)</Label>
                <Input
                  id="weight"
                  type="number"
                  step="0.1"
                  placeholder="65.5"
                  className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]"
                />
              </div>
              <div>
                <Label htmlFor="bmi" className="text-[#0c3555]">BMI</Label>
                <Input
                  id="bmi"
                  type="number"
                  step="0.1"
                  placeholder="22.5"
                  className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]"
                />
              </div>
              <div>
                <Label htmlFor="bp" className="text-[#0c3555]">Blood Pressure</Label>
                <Input
                  id="bp"
                  placeholder="120/80"
                  className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]"
                />
              </div>
            </div>
          </div>

          {/* Boolean Yes/No Fields */}
          <div>
            <h3 className="text-[#0c3555] mb-3 pb-2 border-b border-[#1d9e99]">Medical Conditions</h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="flex items-center gap-4">
                <Label className="text-[#0c3555]">Diabetes:</Label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="diabetes"
                      value="yes"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">Yes</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="diabetes"
                      value="no"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">No</span>
                  </label>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <Label className="text-[#0c3555]">Hypertension:</Label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="hypertension"
                      value="yes"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">Yes</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="hypertension"
                      value="no"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">No</span>
                  </label>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <Label className="text-[#0c3555]">Asthma:</Label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="asthma"
                      value="yes"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">Yes</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="asthma"
                      value="no"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">No</span>
                  </label>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <Label className="text-[#0c3555]">Heart Disease:</Label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="heartDisease"
                      value="yes"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">Yes</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="heartDisease"
                      value="no"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">No</span>
                  </label>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <Label className="text-[#0c3555]">Allergies:</Label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="allergies"
                      value="yes"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">Yes</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="allergies"
                      value="no"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">No</span>
                  </label>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <Label className="text-[#0c3555]">Smoker:</Label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="smoker"
                      value="yes"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">Yes</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="smoker"
                      value="no"
                      className="accent-[#1d9e99]"
                    />
                    <span className="text-sm">No</span>
                  </label>
                </div>
              </div>
            </div>
          </div>

          {/* Previous Medical History - Text Field */}
          <div>
            <h3 className="text-[#0c3555] mb-3 pb-2 border-b border-[#1d9e99]">Previous Medical History</h3>
            <Textarea
              placeholder="Enter detailed medical history, previous diagnoses, treatments, surgeries, etc."
              className="min-h-[120px] border-[#0c3555]/20 focus:border-[#1d9e99]"
            />
          </div>

          {/* Current Medications Table */}
          <div>
            <h3 className="text-[#0c3555] mb-3 pb-2 border-b border-[#1d9e99]">Current Medications</h3>
            <div className="overflow-x-auto border border-[#0c3555]/20 rounded">
              <table className="w-full">
                <thead className="bg-[#1d9e99] text-white">
                  <tr>
                    <th className="px-4 py-2 text-left">Medication Name</th>
                    <th className="px-4 py-2 text-left">Dosage</th>
                    <th className="px-4 py-2 text-left">Frequency</th>
                    <th className="px-4 py-2 text-left">Start Date</th>
                  </tr>
                </thead>
                <tbody>
                  {[1, 2, 3].map((row) => (
                    <tr key={row} className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                      <td className="px-4 py-2">
                        <Input className="border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                      <td className="px-4 py-2">
                        <Input className="border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                      <td className="px-4 py-2">
                        <Input className="border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                      <td className="px-4 py-2">
                        <Input type="date" className="border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Obstetric History Table */}
          <div>
            <h3 className="text-[#0c3555] mb-3 pb-2 border-b border-[#1d9e99]">Obstetric History - Past Pregnancies</h3>
            <div className="overflow-x-auto border border-[#0c3555]/20 rounded">
              <table className="w-full text-sm">
                <thead className="bg-[#1d9e99] text-white">
                  <tr>
                    <th className="px-4 py-3 text-left whitespace-nowrap border-r border-white/20">Field</th>
                    {pregnancyRecords.map((record) => (
                      <th key={record.no} className="px-4 py-3 text-center whitespace-nowrap border-r border-white/20 last:border-r-0">
                        Pregnancy {record.no}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Mode of Conception</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Mode of Delivery</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Sex/Age</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Alive/Dead</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Abortion</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Birth Wt/Kg</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input
                          type="number"
                          step="0.1"
                          className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]"
                        />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Year</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input
                          type="number"
                          className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]"
                        />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Breast Feeding</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    ))}
                  </tr>
                  <tr className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                    <td className="px-4 py-2 bg-[#409f88]/10 border-r border-[#0c3555]/10">
                      <span className="text-[#0c3555]">Anomalies/Com</span>
                    </td>
                    {pregnancyRecords.map((record) => (
                      <td key={record.no} className="px-4 py-2 border-r border-[#0c3555]/10 last:border-r-0">
                        <Input className="min-w-[150px] border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Lab Results Table */}
          <div>
            <h3 className="text-[#0c3555] mb-3 pb-2 border-b border-[#1d9e99]">Laboratory Results</h3>
            <div className="overflow-x-auto border border-[#0c3555]/20 rounded">
              <table className="w-full">
                <thead className="bg-[#1d9e99] text-white">
                  <tr>
                    <th className="px-4 py-2 text-left">Test Name</th>
                    <th className="px-4 py-2 text-left">Result</th>
                    <th className="px-4 py-2 text-left">Normal Range</th>
                    <th className="px-4 py-2 text-left">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {[1, 2, 3, 4].map((row) => (
                    <tr key={row} className="border-t border-[#0c3555]/10 hover:bg-[#f6f5ee]">
                      <td className="px-4 py-2">
                        <Input className="border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                      <td className="px-4 py-2">
                        <Input className="border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                      <td className="px-4 py-2">
                        <Input className="border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                      <td className="px-4 py-2">
                        <Input type="date" className="border-[#0c3555]/20 focus:border-[#1d9e99]" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Clinical Notes */}
          <div>
            <h3 className="text-[#0c3555] mb-3 pb-2 border-b border-[#1d9e99]">Clinical Notes & Observations</h3>
            <Textarea
              placeholder="Enter clinical observations, examination findings, recommendations, etc."
              className="min-h-[120px] border-[#0c3555]/20 focus:border-[#1d9e99]"
            />
          </div>

          {/* Doctor's Signature */}
          <div className="pt-6 border-t border-[#0c3555]/20">
            <div className="grid grid-cols-2 gap-8">
              <div>
                <Label className="text-[#0c3555]">Physician's Name</Label>
                <Input className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]" />
                <div className="mt-4 pt-4 border-t border-[#0c3555]/30">
                  <p className="text-sm text-[#0c3555]/60">Physician's Signature</p>
                </div>
              </div>
              <div>
                <Label className="text-[#0c3555]">Date</Label>
                <Input type="date" className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]" />
                <div className="mt-4">
                  <Label className="text-[#0c3555]">License Number</Label>
                  <Input className="mt-1 border-[#0c3555]/20 focus:border-[#1d9e99]" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-[#409f88] text-white px-8 py-4 text-center text-sm">
          <p>This report is confidential and intended solely for the patient and authorized healthcare providers.</p>
        </div>
      </div>
    </div>
  );
}