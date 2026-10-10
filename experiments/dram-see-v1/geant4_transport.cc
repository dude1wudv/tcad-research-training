// Original minimal EM-only transport model. Not a commercial DRAM process model.
#include "G4RunManager.hh"
#include "G4VUserDetectorConstruction.hh"
#include "G4VModularPhysicsList.hh"
#include "G4EmStandardPhysics_option4.hh"
#include "G4VUserPrimaryGeneratorAction.hh"
#include "G4UserSteppingAction.hh"
#include "G4UserEventAction.hh"
#include "G4ParticleGun.hh"
#include "G4ParticleTable.hh"
#include "G4NistManager.hh"
#include "G4Box.hh"
#include "G4LogicalVolume.hh"
#include "G4PVPlacement.hh"
#include "G4SystemOfUnits.hh"
#include "G4UserLimits.hh"
#include "G4StepLimiterPhysics.hh"
#include "G4Step.hh"
#include "G4Event.hh"
#include "Randomize.hh"
#include <fstream>
#include <iomanip>
#include <cmath>
#include <stdexcept>

struct Config {
  double length, energy, angle;
  std::string particle;
  int seed, events;
  double width() const {return length+0.6;}
  double impact() const {return length+0.45;}
};
class Geometry: public G4VUserDetectorConstruction {
  Config c;
public:
  explicit Geometry(Config config):c(config){}
  G4VPhysicalVolume* Construct() override {
    auto n=G4NistManager::Instance();
    auto world=new G4LogicalVolume(new G4Box("World",10*um,10*um,10*um),n->FindOrBuildMaterial("G4_Galactic"),"World");
    auto pv=new G4PVPlacement(nullptr,{},world,"World",nullptr,false,0);
    auto si=new G4LogicalVolume(new G4Box("Si",c.width()*um/2,1.2*um/2,1.0*um/2),n->FindOrBuildMaterial("G4_Si"),"Si");
    new G4PVPlacement(nullptr,{c.width()*um/2,1.2*um/2,0},si,"Si",world,false,0);
    si->SetUserLimits(new G4UserLimits(0.02*um));
    return pv;
  }
};
class Physics: public G4VModularPhysicsList {
public:
  Physics(){RegisterPhysics(new G4EmStandardPhysics_option4());RegisterPhysics(new G4StepLimiterPhysics());defaultCutValue=0.01*um;}
  void SetCuts() override {SetCutsWithDefault();}
};
class Beam: public G4VUserPrimaryGeneratorAction {
  Config c; G4ParticleGun gun;
public:
  explicit Beam(Config config):c(config),gun(1){}
  void GeneratePrimaries(G4Event* e) override {
    auto p=G4ParticleTable::GetParticleTable()->FindParticle(c.particle);
    if(!p) throw std::runtime_error("Unknown particle");
    double a=c.angle*degree;
    gun.SetParticleDefinition(p);gun.SetParticleEnergy(c.energy*MeV);
    gun.SetParticlePosition({(c.impact()+0.001*std::tan(a))*um,-0.001*um,0});
    gun.SetParticleMomentumDirection({-std::sin(a),std::cos(a),0});
    gun.GeneratePrimaryVertex(e);
  }
};
struct Data {
  std::ofstream steps,summary;
  int event=0;double ion=0,niel=0,track=0;
  Data():steps("steps.csv"),summary("events.csv") {
    steps<<std::setprecision(15)<<"event,track,parent,x_um,y_um,z_um,t_ns,step_um,edep_MeV,niel_MeV,ionizing_MeV\n";
    summary<<std::setprecision(15)<<"event,ionizing_MeV,niel_MeV,primary_path_um\n";
  }
};
class Events:public G4UserEventAction {
  Data& d;
public:
  explicit Events(Data& data):d(data){}
  void BeginOfEventAction(const G4Event* e) override {d.event=e->GetEventID();d.ion=d.niel=d.track=0;}
  void EndOfEventAction(const G4Event*) override {d.summary<<d.event<<','<<d.ion<<','<<d.niel<<','<<d.track<<'\n';}
};
class Steps:public G4UserSteppingAction {
  Data& d;
public:
  explicit Steps(Data& data):d(data){}
  void UserSteppingAction(const G4Step* s) override {
    if(s->GetPreStepPoint()->GetPhysicalVolume()->GetName()!="Si")return;
    double ed=s->GetTotalEnergyDeposit()/MeV, ni=s->GetNonIonizingEnergyDeposit()/MeV;
    double io=std::max(0.0,ed-ni);
    auto t=s->GetTrack();
    if(t->GetParentID()==0)d.track+=s->GetStepLength()/um;
    d.ion+=io;d.niel+=ni;
    if(ed<=0)return;
    auto v=(s->GetPreStepPoint()->GetPosition()+s->GetPostStepPoint()->GetPosition())/2;
    d.steps<<d.event<<','<<t->GetTrackID()<<','<<t->GetParentID()<<','<<v.x()/um<<','<<v.y()/um<<','<<v.z()/um<<','<<s->GetPreStepPoint()->GetGlobalTime()/ns<<','<<s->GetStepLength()/um<<','<<ed<<','<<ni<<','<<io<<'\n';
  }
};
int main(int argc,char**argv){
  if(argc!=7){G4cerr<<"Usage: transport L_um particle E_MeV angle_deg seed events\n";return 2;}
  Config c{std::stod(argv[1]),std::stod(argv[3]),std::stod(argv[4]),argv[2],std::stoi(argv[5]),std::stoi(argv[6])};
  if(c.length<=0||c.energy<=0||c.angle<0||c.angle>45||c.events<1)return 2;
  CLHEP::HepRandom::setTheSeed(c.seed);
  Data d;auto rm=new G4RunManager;
  rm->SetUserInitialization(new Geometry(c));rm->SetUserInitialization(new Physics);
  rm->SetUserAction(new Beam(c));rm->SetUserAction(new Events(d));rm->SetUserAction(new Steps(d));
  rm->Initialize();rm->BeamOn(c.events);delete rm;
  G4cout<<"TRANSPORT_COMPLETED events="<<c.events<<G4endl;
}
